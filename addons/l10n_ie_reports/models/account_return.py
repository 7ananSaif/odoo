from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)

        if country_code == 'IE':
            ec_sales_return_type = self.env.ref('l10n_ie_reports.ie_ec_sales_list_return_type')
            offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
            date_in_previous_period = fields.Date.context_today(self) - relativedelta(months=offset)
            date_from, date_to = ec_sales_return_type._get_period_boundaries(main_company, date_in_previous_period)
            intra_community_taxes = self.env.ref(f'account.{main_company.id}_ie_fp_eu').tax_ids
            domain = [
                ('tax_ids', 'in', intra_community_taxes),
                ('balance', '!=', 0),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('parent_state', '=', 'posted'),
            ]
            if self.env['account.move.line'].search_count(domain, limit=1):
                ec_sales_return_type._try_create_return_for_period(date_from, main_company, tax_unit)

        return rslt
