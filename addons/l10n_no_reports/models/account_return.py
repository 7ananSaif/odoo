from dateutil.relativedelta import relativedelta

from odoo import api, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        months_per_period = return_type._get_periodicity_months_delay(company)

        if return_type_external_id == 'l10n_no_reports.no_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            if months_per_period == 12:
                return date_to + relativedelta(years=1, day=10, month=3)
            else:
                return date_to + relativedelta(days=10) + relativedelta(months=1)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def action_submit(self):
        if self.type_external_id == 'l10n_no_reports.no_tax_return_type':
            return self.env['l10n_no_reports.vat.return.submission.wizard']._open_submission_wizard(self)
        return super().action_submit()
