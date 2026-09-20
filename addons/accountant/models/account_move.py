from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_invoice_in_payment_state(self):
        # OVERRIDE to enable the 'in_payment' state on invoices.
        return 'in_payment'

    def _is_user_able_to_review(self):
        # OVERRIDE of account
        return self.env.user.has_group('account.group_account_user')
