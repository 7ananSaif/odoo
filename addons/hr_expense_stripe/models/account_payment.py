from odoo import models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        # EXTEND account, reconcile stripe moves if available
        res = super().action_post()

        stripe_transactions = {transaction for transaction in self.expense_ids.mapped('stripe_transaction_id') if transaction}
        if stripe_transactions:
            self.env['hr.expense'].search([('stripe_transaction_id', 'in', tuple(stripe_transactions))])._reconcile_stripe_payments()
        return res
