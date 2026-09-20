from odoo import models, fields, api
from odoo.tools.json import scriptsafe as json


class PosPrepOrder(models.Model):
    _inherit = 'pos.prep.order'

    order_otp = fields.Char(compute='_compute_order_otp')
    urban_piper_test = fields.Boolean(compute='_compute_order_otp')

    @api.depends('pos_order_id.delivery_json')
    def _compute_order_otp(self):
        for order in self:
            order.order_otp = ''
            order.urban_piper_test = False
            order_data = json.loads(order.pos_order_id.delivery_json).get('order', {}) if order.pos_order_id.delivery_json else False
            if order_data:
                platform_data = order_data.get(
                    'details', {}).get('ext_platforms') if order.pos_order_id.delivery_json else False

                order.order_otp = platform_data[0].get('id', {}) if platform_data else ''
                order.urban_piper_test = order_data.get('urban_piper_test')
