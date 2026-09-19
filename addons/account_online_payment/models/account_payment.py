from odoo import _, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_draft(self):
        if any(payment.batch_payment_id and payment.payment_method_code == 'sepa_ct' and payment.batch_payment_id.payment_online_status in {'pending', 'accepted'} for payment in self):
            raise UserError(_('You cannot modify a payment that has already been sent to the bank.'))

        return super().action_draft()
