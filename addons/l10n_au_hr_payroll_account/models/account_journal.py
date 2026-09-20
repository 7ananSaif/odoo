from odoo import models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _default_outbound_payment_methods(self):
        res = super()._default_outbound_payment_methods()
        if self._is_payment_method_available('ss_dd'):
            res |= self.env.ref('l10n_au_hr_payroll_account.account_payment_method_ss_dd')
        return res

    def _default_inbound_payment_methods(self):
        res = super()._default_inbound_payment_methods()
        if self._is_payment_method_available('ss_dd'):
            res |= self.env.ref('l10n_au_hr_payroll_account.account_payment_method_ss_dd_refund')
        return res

    def _get_available_payment_method_lines(self, payment_type):
        res = super()._get_available_payment_method_lines(payment_type=payment_type)
        if self.env.context.get('l10n_au_super_payment', False):
            return res
        return res.filtered(lambda l: l.code != 'ss_dd')
