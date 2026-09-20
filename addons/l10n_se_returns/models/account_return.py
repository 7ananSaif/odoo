from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def action_submit(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_se_reports.se_tax_return_type':
            return self.env['l10n_se_returns.vat.return.submission.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'l10n_se_returns.se_ec_sales_list_return_type':
            return self.env['l10n_se_returns.ec.sales.list.submission.wizard']._open_submission_wizard(self)

        return super().action_submit()
