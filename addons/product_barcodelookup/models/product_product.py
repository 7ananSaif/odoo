from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_image_fetch_pending = fields.Boolean(
        help="Whether an image must be fetched for this product. Handled by a cron.",
    )

    @api.onchange('barcode')
    def _onchange_barcode(self):
        for product in self:
            if self.env.user.has_group('base.group_system') and product.barcode and len(product.barcode) > 7:
                barcode_lookup_data = self.product_tmpl_id.barcode_lookup(product.barcode)
                product.product_tmpl_id._update_product_by_barcodelookup(product, barcode_lookup_data)
