from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        # Extends account_reports
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)

        if country_code != 'LT':
            return rslt

        intrastat_return_type = self.env.ref('l10n_lt_intrastat.lt_intrastat_goods_return_type')
        expression_purchase = self.env.ref('l10n_lt.tax_report_line_21_tag')
        expression_sale = self.env.ref('l10n_lt.tax_report_line_18_tag')
        expression_sale_tri = self.env.ref('l10n_lt.tax_report_line_18_triangular_tag')
        expressions = expression_purchase + expression_sale + expression_sale_tri
        today = fields.Date.context_today(self)

        instrastat_date_from = fields.Date.start_of(today - relativedelta(years=1), 'year')
        instrastat_date_to = fields.Date.end_of(today, 'year')

        options = {
            'date': {
                'date_from': fields.Date.to_string(instrastat_date_from),
                'date_to': fields.Date.to_string(instrastat_date_to),
                'filter': 'custom',
                'mode': 'range',
            },
            'selected_variant_id': intrastat_return_type.report_id.id,
            'sections_source_id': intrastat_return_type.report_id.id,
            'tax_unit': 'company_only' if not tax_unit else tax_unit.id,
        }
        company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, intrastat_return_type.report_id)
        options = intrastat_return_type.report_id.with_context(allowed_company_ids=company_ids.ids).get_options(previous_options=options)

        expression_totals_per_col_group = self.env.ref('l10n_lt_reports.lt_tax_return_type').report_id._compute_expression_totals_for_each_column_group(
            expressions,
            options,
            warnings={},
        )

        expression_totals = next(iter(expression_totals_per_col_group.values()))
        balance_purchase = expression_totals.get(expression_purchase, {}).get('value', 0)
        balance_sale = expression_totals.get(expression_sale, {}).get('value', 0) + expression_totals.get(expression_sale_tri, {}).get('value', 0)

        # An intrastat return must be generated if the threshold exceeds 400k in sale or 570k in purchase in the current and last year
        if main_company.currency_id.compare_amounts(balance_sale, 400000) >= 0 or main_company.currency_id.compare_amounts(balance_purchase, 570000) >= 0:
            months_offset = intrastat_return_type._get_periodicity_months_delay(main_company)
            intrastat_return_type._try_create_return_for_period(today - relativedelta(months=months_offset), main_company, tax_unit)

        return rslt
