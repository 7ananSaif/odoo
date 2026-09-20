from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)

        if main_company.is_northern_irish():
            ec_sales_return_type = self.env.ref('l10n_uk_reports.uk_ec_sales_list_return_type')
            offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
            date_in_previous_period = fields.Date.context_today(self) - relativedelta(months=offset)
            date_from, date_to = ec_sales_return_type._get_period_boundaries(main_company, date_in_previous_period)
            intracom_taxes = self.env.ref(f'account.{main_company.id}_account_fiscal_position_ni_to_eu_b2b').tax_ids

            domain = [
                ('tax_ids', 'in', intracom_taxes),
                ('balance', '!=', 0),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('parent_state', '=', 'posted'),
            ]
            if self.env['account.move.line'].search_count(domain, limit=1):
                ec_sales_return_type._try_create_return_for_period(date_from, main_company, tax_unit)

        return rslt


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        if return_type_external_id == 'l10n_uk_reports.uk_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            return date_to + relativedelta(days=7) + relativedelta(months=1)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)
