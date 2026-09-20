# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    wise_transfer_identifier = fields.Char(string='Wise Transfer ID', readonly=True, copy=False)
    wise_unique_reference = fields.Char(string='Wise Unique Reference', readonly=True, copy=False)

    def action_draft(self):
        if any(payment.batch_payment_id and payment.payment_method_code == 'wise_direct_deposit' and payment.batch_payment_id.wise_payment_status not in {'uninitiated'} for payment in self):
            raise UserError(self.env._('You cannot modify a payment that has already been sent to the bank.'))

        return super().action_draft()

    @api.model
    def _get_method_codes_using_bank_account(self):
        res = super()._get_method_codes_using_bank_account()
        res.append('wise_direct_deposit')
        return res

    @api.model
    def _get_method_codes_needing_bank_account(self):
        res = super()._get_method_codes_needing_bank_account()
        res.append('wise_direct_deposit')
        return res
