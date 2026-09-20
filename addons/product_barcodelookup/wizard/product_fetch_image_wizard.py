import base64
import logging
from datetime import timedelta

import requests
from requests.exceptions import ConnectionError as RequestConnectionError, Timeout as RequestTimeout

from odoo import _, api, fields, models
from odoo.exceptions import UserError, RedirectWarning
from odoo.addons.product_barcodelookup.tools import barcode_lookup_service

_logger = logging.getLogger(__name__)


class ProductFetchImageWizard(models.TransientModel):
    _name = 'product.fetch.image.wizard'
    _description = "Fetch product images from Barcode Lookup based on the product's barcode."

    def _check_cron_status(self):
        ir_cron = self.env.ref(
            'product_barcodelookup.ir_cron_fetch_image', raise_if_not_found=False
        )
        if not ir_cron:
            raise UserError(_(
                "The scheduled action \"Product Images: Get product images from Barcode Lookup\" "
                "has been deleted. Please contact your administrator to have the action restored "
                "or to reinstall the module \"product_barcodelookup\"."
            ))
        cron_triggers_count = self.env['ir.cron.trigger'].search_count(
            [('cron_id', '=', ir_cron.id)]
        )
        if cron_triggers_count > 0:
            raise UserError(_(
                "A task to process products in the background is already running. "
                "Please try again later."
            ))
        return True

    def _check_api_key_set(self):
        if not barcode_lookup_service.get_barcode_lookup_key(self):
            action = self.env.ref('base.res_config_setting_act_window')
            msg = _("The API Key for Barcode Lookup must be set in the General Settings.")
            raise RedirectWarning(msg, action.id, _("Go to Settings"))

    @api.model
    def default_get(self, fields):
        self._check_cron_status()
        self._check_api_key_set()

        # Compute default values
        if self.env.context.get('active_model') == 'product.template':
            product_ids = self.env['product.template'].browse(
                self.env.context.get('active_ids')
            ).product_variant_ids
        else:
            product_ids = self.env['product.product'].browse(
                self.env.context.get('active_ids')
            )
        nb_products_selected = len(product_ids)
        products_to_process = product_ids.filtered(lambda p: not p.image_1920 and p.barcode)
        nb_products_to_process = len(products_to_process)
        nb_products_unable_to_process = nb_products_selected - nb_products_to_process
        defaults = super().default_get(fields)
        defaults.update(
            products_to_process=products_to_process,
            nb_products_selected=nb_products_selected,
            nb_products_to_process=nb_products_to_process,
            nb_products_unable_to_process=nb_products_unable_to_process,
        )
        return defaults

    nb_products_selected = fields.Integer(string="Number of selected products", readonly=True)
    products_to_process = fields.Many2many(
        comodel_name='product.product',
        help="The list of selected products that meet the criteria (have a barcode and no image)",
    )
    nb_products_to_process = fields.Integer(string="Number of products to process", readonly=True)
    nb_products_unable_to_process = fields.Integer(
        string="Number of product unprocessable", readonly=True
    )

    def action_fetch_image(self):
        """Fetch the images of the first ten products and delegate the remaining to the cron.

        The first ten images are immediately fetched to improve the user experience. This way, they
        can immediately browse the processed products and be assured that the task is running well.
        Also, if any error occurs, it can be thrown to the user. Then, a cron job is triggered to be
        run as soon as possible, unless the daily request limit has been reached. In that case, the
        cron job is scheduled to run a day later.

        :return: A notification to inform the user about the outcome of the action
        :rtype: dict
        """
        self.products_to_process.is_image_fetch_pending = True  # Flag products to process for the cron

        # Process the first 10 products immediately
        matching_images_count = self._process_products(self._get_products_to_process(10))

        if self._get_products_to_process(1):  # Delegate remaining products to the cron
            self._check_cron_status()
            self.with_context(automatically_triggered=False)._trigger_fetch_images_cron()
            message = _(
                "Products are processed in the background. Images will be updated progressively."
            )
            message_type = 'success'
        else:
            message = _(
                "%(matching_images_count)s matching images have been found for %(product_count)s "
                "products.",
                matching_images_count=matching_images_count,
                product_count=len(self.products_to_process)
            )
            message_type = 'success' if matching_images_count > 0 else 'warning'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Product images"),
                'type': message_type,
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _cron_fetch_image(self):
        """Fetch images of a list of products using their barcode.

        This method is called from a cron job. If the daily request limit is reached,
        the cron job is scheduled to run again a day later.

        :return: None
        """
        # Retrieve 100 products at a time to limit the run time and avoid
        # reaching Barcode Lookup default rate limit.
        self._process_products(self._get_products_to_process(100))
        if self._get_products_to_process(1):
            self.with_context(automatically_triggered=True)._trigger_fetch_images_cron(
                fields.Datetime.now() + timedelta(minutes=1.0)
            )

    def _get_products_to_process(self, limit=100):
        """Get the products that need to be processed and meet the criteria.

        The criteria are to have a barcode and no image. If `products_to_process`,
         is not populated the DB is searched to find matching product records.

        :param int limit: The maximum number of records to return,
                          defaulting to 100 to match, this limit can be changed
                          according to Barcode Lookup API rate limits
        :return: The products that meet the criteria
        :rtype: recordset of `product.product`
        """
        products_to_process = self.products_to_process or self.env['product.product'].search(
            [('is_image_fetch_pending', '=', True)], limit=limit
        )
        return products_to_process.filtered(
            # p.is_image_fetch_pending needed for self.products_to_process's
            # records that might already have been processed but not yet
            # removed from the list when called from action_fetch_image.
            lambda p: not p.image_1920 and p.barcode and p.is_image_fetch_pending
        )[:limit]  # Apply the limit after the filter with self.products_to_process for more results

    def _process_products(self, products_to_process):
        """Fetch an image from the Barcode Lookup API for each product.

        We fetch all image URLs associated with the product and save
        the first valid image.

        :param recordset products_to_process: The products for which an
                                              image must be fetched, as a
                                              `product.product` recordset
        :return: The number of products for which a matching image was found
        :rtype: int
        :raises UserError: If the API Key is incorrect
        """
        if not products_to_process:
            return 0

        nb_timeouts = 0
        batch_size = 10  # Process 10 products at a time
        for i in range(0, len(products_to_process), batch_size):
            # Fetch image URLs and handle eventual errors
            batch_products = products_to_process[i:i + batch_size]
            barcodes = [product.barcode for product in products_to_process]

            try:
                # Fetch 10 products in single request
                response = self._fetch_image_urls_from_barcode_lookup(barcodes)
                response_status_code = response.get('status_code')

                if response_status_code:
                    if response_status_code == requests.codes.forbidden:
                        raise UserError(_(
                            "The Barcode Lookup API key is not set properly or it is invalid. "
                            "Check your API key in setting and retry."
                        ))
                    elif response_status_code == requests.codes.too_many_requests:
                        self.with_context(automatically_triggered=True)._trigger_fetch_images_cron(
                            fields.Datetime.now() + timedelta(days=1.0)
                        )
                        _logger.warning(
                            "Exceeded API call limits. "
                            "Delegating remaining images to next cron run."
                        )
                        break
                    elif response_status_code == requests.codes.not_found:
                        _logger.warning(
                            "No data returned for some barcodes."
                        )
            except (RequestConnectionError, RequestTimeout):
                nb_timeouts += 1
                if nb_timeouts <= 3:  # Temporary loss of service
                    continue  # Let the image of this product be fetched by the next cron run

                # The service has not responded more than 3 times, stop trying for now and wait
                # for the next cron run.
                self.with_context(automatically_triggered=True)._trigger_fetch_images_cron(
                    fields.Datetime.now() + timedelta(hours=1.0)
                )
                _logger.warning(
                    "Encountered too many timeouts. Delegating remaining images to next cron run."
                )
                break

            # Fetch image and handle possible error
            product_response = response.get("products", False)
            for product in batch_products:
                if product_response and product.barcode in product_response and product_response[product.barcode]:
                    for image_link in product_response[product.barcode]:
                        try:
                            image = self._get_image_from_url(image_link)
                            if image:
                                product.image_1920 = image
                            break  # Stop at the first valid image
                        except (
                                RequestConnectionError,
                                RequestTimeout,
                                UserError,  # Raised when the image couldn't be decoded as base64
                                ):
                            pass  # Move on to the next image
                product.is_image_fetch_pending = False
                self.env.cr.commit()  # Commit every image in case the cron is killed

        return len(products_to_process.filtered('image_1920'))

    def _fetch_image_urls_from_barcode_lookup(self, barcodes):
        """Fetch the image URLs.
        :param string barcode: A product's barcode
        :return: A response or None
        :rtype: Response
        """
        if not barcodes:
            return
        barcodes = ",".join(barcodes)  # Comma separated barcodes
        response = self.env['product.template'].with_context(skip_barcode_check=True).barcode_lookup(barcodes)
        product_response = response.get('products', False)
        if product_response:
            products = {}
            # Make a dict with key as barcode and value as list of images
            for product in product_response:
                if all(key in product for key in ['barcode_number', 'images']):
                    products[product.get('barcode_number')] = product.get('images')
            response.update({'products': products})
        return response

    def _get_image_from_url(self, url):
        """Retrieve an image from the URL.

        If the request failed or the response header
        'Content-Type' does not contain 'image/', return None

        :param string url: url of an image
        :return: The retrieved image or None
        :rtype: bytes
        """
        image = None
        response = barcode_lookup_service.barcode_lookup_request(url)
        if response.status_code == requests.codes.ok and 'image/' in response.headers.get('Content-Type', ''):  # Ignore non-image results
            image = base64.b64encode(response.content)
        return image

    def _trigger_fetch_images_cron(self, at=None):
        """Create a trigger for the con `ir_cron_fetch_image`.

        By default the cron is scheduled to be executed as soon as possible but
        the optional `at` argument may be given to delay the execution later
        with a precision down to 1 minute.

        :param Optional[datetime.datetime] at:
            When to execute the cron, at one moments in time instead of as soon as possible.
        """
        cron_fetch_image = self.env.ref('product_barcodelookup.ir_cron_fetch_image')
        if at:
            # Remove all other cron trigger because we don't want to trigger the cron before 'at'
            # in order to respect the time off when timeout or too_many_requests
            self.env['ir.cron.trigger'].search([
                ('call_at', '<', at),
                ('cron_id', '=', cron_fetch_image.id),
            ]).unlink()
        cron_fetch_image._trigger(at)
