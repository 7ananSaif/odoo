from dateutil.relativedelta import relativedelta

from odoo import api, models, fields


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        # EXTENDS account_reports
        res = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)
        if country_code == 'KE':
            withholding_return_type = self.env.ref('l10n_ke_reports.ke_wh_tax_return_type')

            today = fields.Date.context_today(self)
            months_offset = withholding_return_type._get_periodicity_months_delay(main_company)

            tax_tags = withholding_return_type.report_id.line_ids.expression_ids._get_matching_tags()

            periods = [today - relativedelta(months=months_offset * i) for i in range(-1, 4)]
            periods_has_move_lines_map = {
                preiod_bounds: bool(self.env['account.move.line'].search_count([
                    ('tax_tag_ids', 'in', tax_tags.ids),
                    ('company_id', '=', main_company.id),
                    ('date', '>=', preiod_bounds[0]),
                    ('date', '<=', preiod_bounds[1]),
                ], limit=1))
                for preiod_bounds in (
                    withholding_return_type._get_period_boundaries(main_company, period)
                    for period in periods
                )
            }
            for (start, end), has_lines in periods_has_move_lines_map.items():
                if has_lines:
                    withholding_return_type._try_create_return_for_period(start, main_company, tax_unit)

        return res

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        if self.type_external_id in ('l10n_ke_reports.ke_tax_return_type', 'l10n_ke_reports.ke_wh_tax_return_type'):
            tax_tags = self.type_id.report_id.line_ids.expression_ids._get_matching_tags()
            domain.append(('tax_tag_ids', 'in', tax_tags.ids))
        return domain
