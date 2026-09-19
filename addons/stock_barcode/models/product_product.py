# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'
    _barcode_field = 'barcode'

    has_image = fields.Boolean(compute='_compute_has_image')

    @api.depends('has_image')
    def _compute_has_image(self):
        for product in self:
            product.has_image = bool(product.image_128)

    @api.model
    def _search(self, domain, *args, **kwargs):
        # sudo is added for external users to get the products
        domain = self.env.company.sudo().nomenclature_id._preprocess_gs1_search_args(domain, ['product'])
        return super()._search(domain, *args, **kwargs)

    @api.model
    def _get_fields_stock_barcode(self):
        return [
            'barcode',
            'categ_id',
            'code',
            'default_code',
            'display_name',
            'has_image',
            'is_storable',
            'tracking',
            'uom_id',
        ]

    def _get_stock_barcode_specific_data(self):
        return {
            'uom.uom': self.uom_id.read(self.env['uom.uom']._get_fields_stock_barcode(), load=False)
        }
