from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _process_pos_online_payment(self):
        super()._process_pos_online_payment()
        for tx in self.filtered(lambda tx: tx._is_self_order_payment_confirmed()):
            self.env['pos.prep.order'].sudo().process_order(tx.pos_order_id.id)
