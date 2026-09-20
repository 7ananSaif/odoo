from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        """
        Generate all periodic returns for Spain (ES).
        This includes Intrastat returns for goods and services,
        which are only created if sales or purchase balance exceeds the legal threshold (400,000€).
        """

        super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)

        if country_code == 'ES':
            # NOTE: This currently includes triangular sales.
            # TODO: We may want to exclude them in the future using l10n_es_reports_mod349_invoice_type == 'T'.
            tax_return_report = self.env.ref('l10n_es_reports.es_mod303_tax_return_type').report_id
            expression_purchase = self.env.ref('l10n_es.mod_303_casilla_10_balance')
            expression_sale = self.env.ref('l10n_es.mod_303_casilla_59_balance')
            expressions = expression_purchase + expression_sale

            # Date range for the current year
            today = fields.Date.context_today(self)
            intrastat_date_from = fields.Date.start_of(today - relativedelta(years=1), 'year')
            intrastat_date_to = fields.Date.end_of(today, 'year')
            date = {
                'date_from': fields.Date.to_string(intrastat_date_from),
                'date_to': fields.Date.to_string(intrastat_date_to),
                'filter': 'custom',
                'mode': 'range',
            }

            # Evaluate each Intrastat return type
            for return_type in [
                self.env.ref('l10n_es_intrastat.es_intrastat_goods_return_type'),
                self.env.ref('l10n_es_intrastat.es_intrastat_service_return_type'),
            ]:
                # Prepare options for computing return values
                options = {
                    'date': date,
                    'selected_variant_id': return_type.report_id.id,
                    'sections_source_id': return_type.report_id.id,
                    'tax_unit': 'company_only' if not tax_unit else tax_unit.id,
                }
                company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, return_type.report_id)
                options = return_type.report_id.with_context(allowed_company_ids=company_ids.ids).get_options(previous_options=options)
                # Compute the balance for the threshold expressions
                totals_per_group = tax_return_report._compute_expression_totals_for_each_column_group(expressions, options, warnings={})

                totals = next(iter(totals_per_group.values()))
                balance_purchase = totals.get(expression_purchase, {}).get('value') or 0
                balance_sale = totals.get(expression_sale, {}).get('value') or 0

                # The Intrastat return must be generated when either the total sales or total purchases balance is equal to or greater than €400,000.
                if main_company.currency_id.compare_amounts(balance_sale, 400_000) >= 0 or main_company.currency_id.compare_amounts(balance_purchase, 400_000) >= 0:
                    months_offset = return_type._get_periodicity_months_delay(main_company)
                    return_type._try_create_return_for_period(today - relativedelta(months=months_offset), main_company, tax_unit)
