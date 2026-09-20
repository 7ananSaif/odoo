from dateutil.relativedelta import relativedelta

from odoo import api, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        months_per_period = return_type._get_periodicity_months_delay(company)

        if return_type_external_id == 'l10n_pt_reports.pt_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            return date_to + relativedelta(days=10 if months_per_period == 1 else 20) + relativedelta(months=1)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)
