from odoo import api, models


class ProductTemplateAttributeValue(models.Model):
    _name = 'product.template.attribute.value'
    _inherit = ['product.template.attribute.value', 'pos.load.mixin']

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['name', 'attribute_id']
