from odoo import api, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.model
    def _get_method_codes_using_bank_account(self):
        res = super()._get_method_codes_using_bank_account()
        if self.env.company.l10n_in_enet_vendor_batch_payment_feature:
            res += ['enet_rtgs', 'enet_neft', 'enet_fund_transfer', 'enet_demand_draft']
        return res

    @api.model
    def _get_method_codes_needing_bank_account(self):
        res = super()._get_method_codes_needing_bank_account()
        if self.env.company.l10n_in_enet_vendor_batch_payment_feature:
            res += ['enet_rtgs', 'enet_neft', 'enet_fund_transfer', 'enet_demand_draft']
        return res
