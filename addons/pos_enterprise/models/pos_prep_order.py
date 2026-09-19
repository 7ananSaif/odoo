from odoo import fields, models, api
from datetime import timedelta


class PosPrepOrder(models.Model):
    _name = 'pos.prep.order'
    _description = 'Pos Preparation Order'
    _inherit = ['pos.load.mixin']

    pos_order_id = fields.Many2one('pos.order', string='Order', ondelete='cascade')
    prep_line_ids = fields.One2many('pos.prep.line', 'prep_order_id', string='Preparation Lines')
    order_name = fields.Char(compute='_compute_order_name')
    pdis_general_customer_note = fields.Text("General Customer Note", help="Current general-customer-note displayed on preparation display")
    pdis_internal_note = fields.Text("General Note", help="Current general-note displayed on preparation display")
    completion_time = fields.Integer("Completion Time", help="Time in minutes to complete the order (preparation + service time)")

    @api.depends('pos_order_id.floating_order_name')
    def _compute_order_name(self):
        for order in self:
            order.order_name = order.pos_order_id.floating_order_name if order.pos_order_id.floating_order_name else order.pos_order_id.tracking_number

    @api.model
    def process_order(self, order_id, options={}):
        if not order_id or not self.env['pos.order'].browse(order_id).exists():
            return

        order = self.env['pos.order'].browse(order_id)
        data = order._process_preparation_changes(options)
        if not data['change']:
            return

        for p_dis in self.env['pos.prep.display']._get_preparation_displays(order, data['category_ids']):
            p_dis._send_load_orders_message(data['sound'], data.get('notification'), order_id)

        return True

    @api.model
    def _clean_preparation_data(self):
        orders = self.env['pos.prep.order'].search([('write_date', '<=', fields.Datetime.now() - timedelta(days=1))])
        orders.unlink()
        return True
