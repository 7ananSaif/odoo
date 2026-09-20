from odoo import models, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['pos_categ_ids', 'display_name']
