from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        # Extends account_reports
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)

        if country_code == 'DK':
            ec_sales_return_type = self.env.ref('l10n_dk_reports.dk_ec_sales_list_return_type')
            months_offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
            previous_period_start, previous_period_end = ec_sales_return_type._get_period_boundaries(main_company, fields.Date.context_today(self) - relativedelta(months=months_offset))
            company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, ec_sales_return_type.report_id)

            ec_sales_list_tag_ids = [
                *self.env.ref('l10n_dk.account_tax_report_line_section_b_product_eu_tag')._get_matching_tags().ids,
                *self.env.ref('l10n_dk.account_tax_report_line_section_b_services_tag')._get_matching_tags().ids,
            ]

            need_ec_sales_list = self.env['account.move.line'].search_count([
                ('tax_tag_ids', 'in', ec_sales_list_tag_ids),
                ('company_id', 'in', company_ids.ids),
                ('date', '>=', previous_period_start),
                ('date', '<=', previous_period_end),
            ], limit=1)

            if need_ec_sales_list:
                ec_sales_return_type._try_create_return_for_period(previous_period_start, main_company, tax_unit)

        return rslt
