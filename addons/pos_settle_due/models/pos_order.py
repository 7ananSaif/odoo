from odoo import models, fields, api, _

class PosOrder(models.Model):
    _inherit = 'pos.order'

    customer_due_total = fields.Monetary(string="Due", compute="_compute_customer_due_total", store=True, currency_field="currency_id")
    init_customer_due_total = fields.Monetary(string="Initial due (before any settlement)", currency_field="currency_id")
    settled_order_line_ids = fields.One2many("pos.order.line", "settled_order_id", string="Settled Order Lines")
    settled_orders_count = fields.Integer(string="Number of settled orders", compute='_compute_settled_orders_count', store=True)
    commercial_partner_id = fields.Many2one(comodel_name="res.partner", related="partner_id.commercial_partner_id", readonly=True, store=True)

    @api.depends('payment_ids', 'settled_order_line_ids', 'is_invoiced')
    def _compute_customer_due_total(self):
        for order in self:
            order_pay_later_pm = order.payment_ids.filtered(lambda payment: payment.amount > 0 and payment.payment_method_id.type == 'pay_later')
            # Only compute potential customer due if there is a partner and there is a pay_later payment method and if the order is not invoiced
            if order.partner_id and order_pay_later_pm and not order.is_invoiced:
                if order.customer_due_total:
                    # Update the existing due of the order
                    order_due = order.init_customer_due_total
                    order_settled = self.env.company.currency_id.round(
                        sum(order.settled_order_line_ids.mapped('price_unit'))
                    )
                    order.customer_due_total = order_due - order_settled
                else:
                    order_due = sum(order.payment_ids.filtered(lambda payment: payment.amount > 0 and payment.payment_method_id.type == 'pay_later').mapped('amount'))
                    customer_due = order.partner_id.get_total_due(order.config_id.id)['res.partner'][0]['total_due']
                    total_before = customer_due - order_due
                    if customer_due > 0:
                        if total_before < 0:
                            # If the customer had a deposited amount
                            order_due = customer_due
                        if order_due > 0:
                            order.customer_due_total = order_due
                            order.init_customer_due_total = order_due
            else:
                order.customer_due_total = 0

    @api.depends('settled_order_line_ids')
    def _compute_settled_orders_count(self):
        for order in self:
            order.settled_orders_count = len(order.settled_order_line_ids)

    def action_view_settled_orders(self):
        return {
            'name': _('Settled Orders'),
            'view_mode': 'list,form',
            'res_model': 'pos.order',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.mapped('settled_order_line_ids.order_id').ids)],
        }
