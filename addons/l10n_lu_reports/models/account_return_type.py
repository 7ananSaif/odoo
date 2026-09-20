from dateutil.relativedelta import relativedelta
from odoo import fields, models


class AccountReturnType(models.Model):
    _name = 'account.return.type'
    _inherit = 'account.return.type'

    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        if country_code == 'LU':
            ec_sales_list_return_type = self.env.ref('l10n_lu_reports.lu_ec_sales_list_return_type')
            months_offset = ec_sales_list_return_type._get_periodicity_months_delay(main_company)
            previous_period_start, previous_period_end = ec_sales_list_return_type._get_period_boundaries(main_company, fields.Date.context_today(self) - relativedelta(months=months_offset))
            tax_tags = self.env['l10n_lu.ec.sales.report.handler']._get_tax_tags_for_lux_sales_report()
            tax_tags = [*tax_tags['goods'], *tax_tags['triangular'], *tax_tags['services']]
            company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, ec_sales_list_return_type.report_id)

            need_ec_sales_list = bool(self.env['account.move.line'].search_count([
                ('tax_tag_ids', 'in', tax_tags),
                ('company_id', 'in', company_ids.ids),
                ('date', '>=', previous_period_start),
                ('date', '<=', previous_period_end),
            ], limit=1))

            if need_ec_sales_list:
                ec_sales_list_return_type._try_create_return_for_period(previous_period_start, main_company, tax_unit)

        return super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)
