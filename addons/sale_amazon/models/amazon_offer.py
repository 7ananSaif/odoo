# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import split_every

from odoo.addons.sale_amazon import utils as amazon_utils


_logger = logging.getLogger(__name__)


class AmazonOffer(models.Model):
    _name = 'amazon.offer'
    _description = "Amazon Offer"

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)

        # Default account_id.
        if not result.get('account_id'):
            accounts = self.env['amazon.account'].search([
                ('refresh_token', '!=', False),
                *self.env['amazon.account']._check_company_domain(self.env.company),
            ], limit=2)
            if len(accounts) == 1:
                result['account_id'] = accounts.id

        # Default marketplace_id.
        if (account_id := result.get('account_id')) and not result.get('marketplace_id'):
            account = self.env['amazon.account'].browse(account_id)
            if len(marketplaces := account.active_marketplace_ids) == 1:
                result['marketplace_id'] = marketplaces.id

        return result

    account_id = fields.Many2one(
        string="Account",
        help="The seller account used to manage this product.",
        comodel_name='amazon.account',
        required=True,
        index=True,
        ondelete='cascade',
    )  # The default account provided in the context of the list view.
    company_id = fields.Many2one(related='account_id.company_id', readonly=True)
    active_marketplace_ids = fields.Many2many(related='account_id.active_marketplace_ids')
    marketplace_id = fields.Many2one(
        string="Marketplace",
        help="The marketplace of this offer.",
        comodel_name='amazon.marketplace',
        required=True,
        domain="[('id', 'in', active_marketplace_ids)]",
    )
    product_id = fields.Many2one(
        string="Product", comodel_name='product.product', required=True, ondelete='cascade'
    )
    product_template_id = fields.Many2one(
        related="product_id.product_tmpl_id", store=True, readonly=True
    )
    sku = fields.Char(string="Amazon SKU", help="The Stock Keeping Unit.", required=True)
    amazon_sync_status = fields.Selection(
        string="Amazon Synchronization Status",
        help="The synchronization status of the product's stock level to Amazon:\n"
             "- Processing: The stock level has been sent and is being processed.\n"
             "- Done: The stock level has been processed.\n"
             "- Error: The synchronization of the stock level failed.\n"
             "- Reset: The next stock synchronization will reset the FBM stock level to 0.",
        selection=[
            ('processing', "Processing"),
            ('done', "Done"),
            ('error', "Error"),
            ('reset', "Reset FBM stock"),
        ],
        readonly=True,
    )
    amazon_feed_ref = fields.Char(string="Amazon Feed Reference", readonly=True)
    amazon_channel = fields.Selection(
        string="Fulfillment Channel",
        help="The channel will be updated with the incomming orders or during the next stock"
        " synchronization.",
        selection=[('fbm', "Fulfilled by Merchant"), ('fba', "Fulfilled by Amazon")],
        readonly=True,
    )
    sync_stock = fields.Boolean(
        string="Stock Synchronization", compute='_compute_sync_stock', store=True, readonly=False,
    )

    _unique_sku = models.Constraint(
        'UNIQUE(account_id, sku)',
        "SKU must be unique for a given account.",
    )

    @api.depends('amazon_channel', 'account_id.synchronize_inventory', 'product_id.is_storable')
    def _compute_sync_stock(self):
        for offer in self:
            offer.sync_stock = (
                offer.account_id.synchronize_inventory
                and offer.product_id.is_storable
                and (not offer.amazon_channel or offer.amazon_channel == 'fbm')
            )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """ Set the SKU to the internal reference of the product if it exists. """
        for offer in self:
            offer.sku = offer.product_id.default_code

    @api.constrains('sync_stock')
    def _check_product_is_storable(self):
        for offer in self.filtered('sync_stock'):
            if not offer.product_id.is_storable:
                raise ValidationError(self.env._("Non-storable product cannot be synced."))

    def action_view_online(self):
        self.ensure_one()
        url = f'{self.marketplace_id.seller_central_url}/skucentral?mSku={self.sku}'
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def _get_feed_data(self):
        """Load the necessary data for the inventory feed, and fetch the missing ones when possible.

        :return: A dictionary per offer in `self` containing at least the Amazon product type.
        :rtype: dict[amazon.offer, dict['productType: str, ...]]
        """
        feed_data_by_offer = {}
        for offer in self:
            try:
                feed_data = json.loads(offer.amazon_feed_ref)
            except (json.JSONDecodeError, TypeError):  # Field is either incorrect JSON, or False
                feed_data = None
            if isinstance(feed_data, dict):  # In case old `amazon_feed_ref` are still stored
                feed_data_by_offer[offer] = feed_data

        feed_data_by_offer.update(
            self.filtered(lambda o: not (
                o in feed_data_by_offer
                and 'productType' in feed_data_by_offer[o]
                and o.amazon_channel
            ))._fetch_and_save_feed_data()  # Fetch missing data
        )

        return feed_data_by_offer

    def _fetch_and_save_feed_data(self):
        """Fetch data necessary for the inventory feed to work and save it in the record.

        Necessary data are:
            - productType: Amazon product type
            - amazon_channel: fulfillment channel

        :return: A mapping of offer to feed data
        :rtype: dict['amazon.offer', dict]
        """
        feed_data_by_offer = {}
        to_fetch = self.sorted(lambda o:
            o.amazon_sync_status in ('reset', 'error')  # Fetch priority offers first
        ).grouped(lambda o: (o.account_id, o.marketplace_id))
        # `searchListingsItems` only supports up to 20 SKUs
        to_fetch = (
            (group, batch)
            for group, offers in to_fetch.items()
            for batch in split_every(20, offers.ids, self.env['amazon.offer'].browse)
        )
        for (account_id, marketplace_id), offers in to_fetch:
            try:
                response = amazon_utils.make_sp_api_request(
                    account=account_id,
                    operation='searchListingsItems',
                    path_parameter=account_id.seller_key,
                    payload={
                        'marketplaceIds': marketplace_id.api_ref,
                        'includedData': 'attributes,productTypes',
                        'identifiersType': 'SKU',
                        'identifiers': ','.join(offer.sku.replace(',', '') for offer in offers),
                        'pageSize': len(offers),
                    },
                )
            except amazon_utils.AmazonRateLimitError:
                _logger.warning("Could not fetch every offers infos due to rate limit from Amazon.")
                # Mark failed offers, to be prioritized on next try
                offers.filtered(
                    lambda o: o.amazon_sync_status != 'reset'
                ).amazon_sync_status = 'error'
                continue

            # Parse product data
            offer_by_sku = offers.grouped('sku')
            # Default to FBA to not fetch the info everytime when the offer isn't found by Amazon
            offers.amazon_channel = 'fba'
            feed_data_by_offer.update({offer: {'productType': False} for offer in offers})
            for item in response['items']:
                offer = offer_by_sku[item['sku']]
                feed_data_by_offer[offer]['productType'] = (
                    item['productTypes'] and item['productTypes'][0]['productType']
                    or 'PRODUCT'
                )
                is_fbm = 'merchant_shipping_group' in item['attributes']
                offer.amazon_channel = 'fbm' if is_fbm else 'fba'
                if is_fbm and offer.amazon_sync_status == 'reset':
                    offer.amazon_sync_status = False  # Reset only applies to FBA offers

        # Save data to reduce api calls
        AmazonOffer._save_feed_data(feed_data_by_offer)

        return feed_data_by_offer

    @classmethod
    def _save_feed_data(cls, feed_data_by_offer):
        """Save inventory feed data.

        :param dict['amazon.offer', dict] feed_data_by_offer: A mapping from offer to data necessary
            for the inventory feed.
        """
        for offer, feed_info in feed_data_by_offer.items():
            offer.amazon_feed_ref = json.dumps(feed_info, separators=(',', ':'))

    def _update_inventory_availability(self, account):
        """Update the stock quantity of Amazon products to Amazon.

        :param amazon.account account: The Amazon account to which the stock update should apply.
        """
        feed_data_by_offer = self._get_feed_data()
        # `_get_feed_data` can fail for some offers (rate limit)
        offers_to_sync = self.filtered(lambda o: o in feed_data_by_offer)

        # Inventory feed can only apply to one marketplace
        for marketplace_id, offers in offers_to_sync.grouped('marketplace_id').items():
            offers._send_inventory_feed(
                account,
                {o: feed_data_by_offer[o] for o in offers},
                marketplace_id,
            )

    def _send_inventory_feed(self, account, feed_data_by_offer, marketplace_id):
        """Send the inventory feed for the given marketplace.

        Note: A feed of type `JSON_LISTINGS_FEED` can be applied to only one marketplace.

        :param 'amazon.account' account: The Amazon account on behalf of which the feed should be
            built and submitted.
        :param dict['amazon.offer', dict] feed_data_by_offer: A mapping of offer to their feed data,
            i.e. at least the 'productType' of the offer.
        :param 'amazon.marketplace' marketplace_id: The marketplace to which the feed should apply.
        """
        if not self:  # Don't send empty feed
            return

        for i, feed_info in enumerate(feed_data_by_offer.values(), start=1):
            # Assign and save the message id to later match error message(s)
            feed_info['messageId'] = i
        messages = self._build_feed_messages(feed_data_by_offer)
        json_feed = amazon_utils.build_json_feed(account, messages)
        try:
            feed_ref = amazon_utils.submit_feed(
                account,
                json_feed,
                'JSON_LISTINGS_FEED',
                feed_content_type='application/json; charset=UTF-8',
                marketplace_api_refs=[marketplace_id.api_ref],
            )
        except amazon_utils.AmazonRateLimitError:
            _logger.info(
                "Rate limit reached while sending inventory availability notification for Amazon"
                " account with id %s.", account.id
            )
        else:
            _logger.info(
                "Sent inventory availability notification (feed_ref %s) to Amazon for account ID"
                " %s. SKUs: %s.",
                feed_ref,
                account.id,
                ', '.join(self.mapped('sku')),
            )
            self.amazon_sync_status = 'processing'
            # Save feed reference to later sync any error that might have occurred
            for feed_info in feed_data_by_offer.values():
                feed_info['amazon_feed_ref'] = feed_ref
            # Save message IDs
            self._save_feed_data(feed_data_by_offer)

    def _build_feed_messages(self, feed_data_by_offer):
        """Constructs the inventory feed messages.

        :param dict['amazon.offer', dict] feed_data_by_offer: A dict mapping offer with the
            necessary feed data, i.e. productType and messageId.
        :rtype: list[dict]
        """
        return [
            {
                'messageId': feed_data['messageId'],
                'sku': offer.sku,
                'operationType': 'PARTIAL_UPDATE',
                'productType': feed_data['productType'],
                'attributes': {
                    'fulfillment_availability': [{
                        'fulfillment_channel_code': 'DEFAULT',
                        'quantity': (
                            0 if offer.amazon_sync_status == 'reset'
                            else max(int(offer._get_available_product_qty()), 0)
                        ),
                    }]
                }
            }
            for offer, feed_data in feed_data_by_offer.items()
        ]

    def _get_available_product_qty(self):
        """ Retrieve the current available and free product quantity.

        This hook can be overridden to set a finer quantity.

        :return: The free quantity.
        :rtype: float
        """
        self.ensure_one()
        return self.product_id.free_qty
