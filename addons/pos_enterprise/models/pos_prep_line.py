from odoo import fields, models


class PosPrepLine(models.Model):
    _name = 'pos.prep.line'
    _description = 'Pos Preparation Line'
    _inherit = ['pos.load.mixin']

    prep_order_id = fields.Many2one('pos.prep.order', string='Preparation Order', required=True, index=True, ondelete='cascade')
    quantity = fields.Float('Quantity', required=True)
    cancelled = fields.Float("Quantity of cancelled product")
    pos_order_line_uuid = fields.Char(help="Original pos order line UUID")
    internal_note = fields.Char(help="Internal notes written at the time of the order")
    customer_note = fields.Char(help="Customer notes written at the time of the order")
    product_id = fields.Many2one('product.product', string="Product ID")
    attribute_value_ids = fields.Many2many('product.template.attribute.value', 'pos_prep_line_product_template_attribute_value_rel', string="Selected Attributes")
    combo_line_ids = fields.One2many('pos.prep.line', 'combo_parent_id', string="Combo Lines")
    combo_parent_id = fields.Many2one('pos.prep.line', string="Parent Combo Line", help="Indicates the parent line if this is part of a combo", index='btree_not_null')
    pos_order_line_id = fields.Many2one('pos.order.line', string="Original pos order line")
