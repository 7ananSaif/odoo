from odoo import models, api, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    pos_order_line_ids = fields.One2many('pos.order.line', 'settled_invoice_id', string="Order lines settling the invoice")
    pos_amount_unsettled = fields.Monetary(
        string="Amount To Pay In POS",
        compute='_compute_pos_amount_unsettled',
        store=True,
    )

    @api.model
    def _load_pos_data_fields(self, config):
        return ['name', 'amount_residual', 'pos_amount_unsettled']

    @api.model
    def _load_pos_data_domain(self, data, config):
        return False

    @api.depends('pos_order_line_ids', 'amount_residual_signed')
    def _compute_pos_amount_unsettled(self):
        for invoice in self:
            total_pos_paid = sum(invoice.pos_order_line_ids.filtered(
                lambda line: line.order_id.session_id.state != 'closed'
            ).mapped('price_unit'))
            invoice.pos_amount_unsettled = invoice.amount_residual_signed - total_pos_paid
