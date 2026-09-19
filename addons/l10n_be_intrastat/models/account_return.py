from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):

        if country_code == 'BE':
            intrastat_return_type = self.env.ref('l10n_be_intrastat.be_intrastat_goods_return_type')
            expression = self.env.ref('l10n_be.tax_report_line_46L_tag')
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

            expression_totals_per_col_group = self.env.ref('l10n_be_reports.be_vat_return_type').report_id._compute_expression_totals_for_each_column_group(
                expression,
                options,
                warnings={}
            )

            expression_totals = next(iter(expression_totals_per_col_group.values()))
            balance = expression_totals.get(expression, {}).get('value', 0)

            # An intrastat return must be generated if the threshold exceeds 1000000 in the current and last year
            if main_company.currency_id.compare_amounts(balance, 1000000) >= 0:
                months_offset = intrastat_return_type._get_periodicity_months_delay(main_company)
                intrastat_return_type._try_create_return_for_period(today - relativedelta(months=months_offset), main_company, tax_unit)

        return super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def action_submit(self):
        if self.type_external_id == 'l10n_be_intrastat.be_intrastat_goods_return_type':
            return self.env['l10n_be_intrastat.intrastat.goods.submission.wizard']._open_submission_wizard(self)

        return super().action_submit()

    def _generate_locking_attachments(self, options):
        super()._generate_locking_attachments(options)
        if self.type_external_id == 'l10n_be_intrastat.be_intrastat_goods_return_type':
            self._add_attachment(self.type_id.report_id.dispatch_report_action(options, 'be_intrastat_export_to_xml'))
            self._add_attachment(self.type_id.report_id.dispatch_report_action(options, 'be_intrastat_export_to_csv'))
