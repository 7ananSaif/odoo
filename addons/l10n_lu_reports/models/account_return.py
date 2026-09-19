from dateutil.relativedelta import relativedelta

from odoo import api, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        if return_type_external_id == 'l10n_lu_reports.lu_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            return date_to + relativedelta(days=15) + relativedelta(months=1)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def action_submit(self):
        # Extends account.return
        self.ensure_one()

        if self.type_external_id == 'l10n_lu_reports.lu_tax_return_type':
            return self.env['l10n_lu_reports.tax.return.submission.wizard']._open_submission_wizard(self)
        if self.type_external_id == 'l10n_lu_reports.lu_ec_sales_list_return_type':
            return self.env['l10n_lu_reports.ec.sales.list.submission.wizard']._open_submission_wizard(self)
        return super().action_submit()
