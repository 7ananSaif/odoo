from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        if return_type_external_id == 'l10n_gr_reports.gr_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            deadline_date = fields.Date.end_of(date_to + relativedelta(months=1), 'month')
            weekday = deadline_date.weekday()
            if weekday > 4:
                deadline_date += relativedelta(days=4 - weekday)
            return deadline_date

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)
