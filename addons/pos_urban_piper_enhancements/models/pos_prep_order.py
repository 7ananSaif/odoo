from odoo import models, fields, api


class PosPrepOrder(models.Model):
    _inherit = 'pos.prep.order'

    delivery_datetime = fields.Char(compute='_compute_delivery_datetime')

    @api.depends('pos_order_id.delivery_json')
    def _compute_delivery_datetime(self):
        for order in self:
            order.delivery_datetime = order.pos_order_id.delivery_datetime.timestamp() * 1000 if order.pos_order_id.delivery_datetime else ''
