from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        # EXTENDS account_reports
        if country_code == 'FR':
            intrastat_report_types = (
                self.env.ref('l10n_fr_intrastat.l10n_fr_intrastat_goods_return_type'),
                self.env.ref('l10n_fr_intrastat.l10n_fr_intrastat_services_return_type'),
            )
            expression = self.env.ref('l10n_fr_account.tax_report_F2_balance_from_tags')
            today = fields.Date.context_today(self)

            for report_type in intrastat_report_types:
                months_offset = report_type._get_periodicity_months_delay(main_company)
                previous_period_start, previous_period_end = report_type._get_period_boundaries(main_company, today - relativedelta(months=months_offset))
                date = {
                    'date_from': previous_period_start,
                    'date_to': previous_period_end,
                    'filter': 'custom',
                    'mode': 'range',
                }

                options = {
                    'date': date,
                    'selected_variant_id': report_type.report_id.id,
                    'sections_source_id': report_type.report_id.id,
                    'tax_unit': 'company_only' if not tax_unit else tax_unit.id,
                }
                company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, report_type.report_id)
                options = report_type.report_id.with_context(allowed_company_ids=company_ids.ids).get_options(previous_options=options)

                expression_totals_per_col_group = self.env.ref('l10n_fr_reports.vat_return_type').report_id._compute_expression_totals_for_each_column_group(
                    expression,
                    options,
                    warnings={},
                )

                expression_totals = next(iter(expression_totals_per_col_group.values()))
                balance = expression_totals.get(expression, {}).get('value', 0)

                # An intrastat return must be generated if the threshold exceeds 460000€
                if main_company.currency_id.compare_amounts(balance, 460000) >= 0:
                    report_type._try_create_return_for_period(previous_period_start, main_company, tax_unit)

        return super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)
