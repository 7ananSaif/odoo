# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _compute_outstanding_account_id(self):
        # EXTENDS account
        super_payments = self.filtered(lambda payment: payment.payment_method_code == 'ss_dd')
        for payment in super_payments:
            payment.outstanding_account_id = self.env["l10n_au.super.stream"]._get_default_payment_account(payment.payment_method_line_id)
        super(AccountPayment, self - super_payments)._compute_outstanding_account_id()
