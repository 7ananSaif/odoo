from odoo import models


class HrExpenseSplit(models.TransientModel):
    _name = 'hr.expense.split'
    _inherit = ['hr.expense.split']

    def _get_values(self):
        values = super()._get_values()
        # Add any additional fields or modifications specific to hr_expense_stripe here
        values.update({
            'stripe_authorization_id': self.expense_id.stripe_authorization_id,
            'stripe_transaction_id': self.expense_id.stripe_transaction_id,
            'card_id': self.expense_id.card_id.id,
        })
        return values
