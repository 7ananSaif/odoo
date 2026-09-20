from odoo import api, models


class ProductAttributeCustomValue(models.Model):
    _name = 'product.attribute.custom.value'
    _inherit = ['product.attribute.custom.value', 'pos.load.mixin']

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['custom_value', 'custom_product_template_attribute_value_id', 'pos_order_line_id']
