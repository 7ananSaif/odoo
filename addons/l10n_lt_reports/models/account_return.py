from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def action_submit(self):
        if self.type_external_id == 'l10n_lt_reports.lt_tax_return_type':
            return self.env['l10n_lt_reports.vat.return.submission.wizard']._open_submission_wizard(self)
        if self.type_external_id == 'l10n_lt_reports.lt_ec_sales_list_return_type':
            return self.env['l10n_lt_reports.ec.sales.list.submission.wizard']._open_submission_wizard(self)
        return super().action_submit()
