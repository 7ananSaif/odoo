# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_booking_fee = fields.Boolean(compute='_compute_is_booking_fee', compute_sudo=True)

    def _compute_is_booking_fee(self):
        service_products = self.filtered(lambda pp:
            pp.type == 'service'
            and pp.sale_ok
            and pp.service_tracking == 'no'
        )
        (self - service_products).is_booking_fee = False
        if not service_products:
            return
        has_appointment_type_per_product = {
            product.id: bool(count)
            for product, count in self.env['appointment.type']._read_group(
                domain=[
                    ('has_payment_step', '=', True),
                    ('product_id', 'in', service_products.ids),
                ],
                groupby=['product_id'],
                aggregates=['__count'],
            )
        }
        for product in service_products:
            product.is_booking_fee = has_appointment_type_per_product.get(product.id, False)

    def _can_return_content(self, field_name=None, access_token=None):
        """ Override of `orm` to give public users access to the unpublished product image.

        Give access to the public users to the unpublished product images if they are linked to an
        appointement type.

        :param field_name: The name of the field to check.
        :param access_token: The access token.
        :return: Whether to allow the access to the image.
        :rtype: bool
        """
        if (
            field_name in ["image_%s" % size for size in [1920, 1024, 512, 256, 128]]
            and self.sudo().is_booking_fee
        ):
            return True
        return super()._can_return_content(field_name, access_token)

    def _get_product_placeholder_filename(self):
        if self.sudo().is_booking_fee:
            return 'appointment_account_payment/static/src/img/booking_product.png'
        return super()._get_product_placeholder_filename()
