from odoo import api, models
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)

        oss_tax_domain = [
            ('repartition_line_ids.tag_ids', 'in', self.env.ref('l10n_eu_oss.tag_oss').ids),
            ('country_id.code', '=', country_code),
            *self.env['account.tax']._check_company_domain(main_company),
        ]

        # Only do that when instantiating the domestic returns, to avoid double computation in case of multivat
        if self.env['account.tax'].search_count([*oss_tax_domain, ('type_tax_use', '=', 'sale')], limit=1):
            self.env.ref('l10n_eu_oss_reports.eu_oss_sales_tax_return_type')._try_create_returns_for_fiscal_year(main_company, tax_unit=tax_unit)

        if self.env['account.tax'].search_count([*oss_tax_domain, ('type_tax_use', '=', 'purchase')], limit=1):
            self.env.ref('l10n_eu_oss_reports.eu_oss_imports_tax_return_type')._try_create_returns_for_fiscal_year(main_company, tax_unit=tax_unit)

        return rslt

    def _can_return_exist(self, company, tax_unit=False):
        can_exist = super()._can_return_exist(company, tax_unit=tax_unit)
        if tax_unit and self in (
            self.env.ref('l10n_eu_oss_reports.eu_oss_sales_tax_return_type'),
            self.env.ref('l10n_eu_oss_reports.eu_oss_imports_tax_return_type'),
        ):
            can_exist &= tax_unit.main_company_id == company
        return can_exist


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _get_amount_to_pay_additional_tax_domain(self):
        oss_domain = [('repartition_line_ids', 'any', [('tag_ids', 'in', self.env.ref('l10n_eu_oss.tag_oss').ids)])]

        if self.type_external_id in ('l10n_eu_oss_reports.eu_oss_sales_tax_return_type', 'l10n_eu_oss_reports.eu_oss_imports_tax_return_type'):
            return oss_domain
        else:
            return [*super()._get_amount_to_pay_additional_tax_domain(), '!', *oss_domain]

    def _get_vat_closing_entry_additional_domain(self):
        if self.type_external_id == 'l10n_eu_oss_reports.eu_oss_sales_tax_return_type':
            domain = [
                ('tax_line_id', '!=', False),
                *self.env['l10n_eu_oss.sales.tax.report.handler']._get_oss_custom_domain(),
            ]
            return domain
        elif self.type_external_id == 'l10n_eu_oss_reports.eu_oss_imports_tax_return_type':
            return [
                ('tax_line_id', '!=', False),
                *self.env['l10n_eu_oss.imports.tax.report.handler']._get_oss_custom_domain(),
            ]

        # remove oss taxes from normal closings
        domain = super()._get_vat_closing_entry_additional_domain()
        domain += [('tax_tag_ids', 'not in', self.env.ref('l10n_eu_oss.tag_oss').ids)]
        return domain

    def action_submit(self):
        oss_wizard_country_codes = ('BE', 'LU')
        oss_return_types = ('l10n_eu_oss_reports.eu_oss_sales_tax_return_type', 'l10n_eu_oss_reports.eu_oss_imports_tax_return_type')
        if self.company_id.account_fiscal_country_id.code in oss_wizard_country_codes and self.type_external_id in oss_return_types:
            return self.env['l10n_eu_oss_reports.return.submission.wizard']._open_submission_wizard(self)

        return super().action_submit()

    def _run_checks(self, check_codes_to_ignore):
        checks = super()._run_checks(check_codes_to_ignore)

        if self.type_external_id == 'l10n_eu_oss_reports.eu_oss_sales_tax_return_type':
            checks += self._check_suite_oss_sales(check_codes_to_ignore)

        return checks

    def _check_suite_oss_sales(self, check_codes_to_ignore):
        checks = []

        if 'check_oss_currency' not in check_codes_to_ignore:
            checks.append({
                'code': 'check_oss_currency',
                'name': _lt("EUR Currency"),
                'message': _lt("OSS reports must be submitted in euros."),
                'result': 'reviewed' if self.company_id.currency_id.name == 'EUR' else 'anomaly',
            })

        if 'check_oss_only_intra_eu_transactions' not in check_codes_to_ignore:
            checks.append({
                'code': 'check_oss_only_intra_eu_transactions',
                'name': _lt("Only intra-EU transactions"),
                'message': _lt("Exclude any domestic or extra-EU sales from the OSS report."),
                'result': 'reviewed',
            })

        if 'check_oss_only_b2c_customer' not in check_codes_to_ignore:
            report_options = self._get_closing_report_options()
            options_domain = self.type_id.report_id._get_options_domain(report_options, 'strict_range')

            business_partner_ids = [
                group_result[0].id
                for group_result in self.env['account.move.line'].sudo()._read_group(
                    domain=[
                        *options_domain,
                        *self._get_vat_closing_entry_additional_domain(),
                        ('partner_id.is_company', '=', True),
                    ],
                    groupby=['partner_id'],
                )
            ]

            business_partners_count = len(business_partner_ids)
            review_action = {
                'type': 'ir.actions.act_window',
                'view_mode': 'list',
                'res_model': 'res.partner',
                'domain': [('id', 'in', business_partner_ids)],
                'views': [[False, 'list'], [False, 'form']],
            }

            checks.append({
                'code': 'check_oss_only_b2c_customer',
                'name': _lt("Only B2C transactions"),
                'message': _lt("Only B2C transactions should be included in the OSS report."),
                'records_count': business_partners_count,
                'records_model': self.env['ir.model']._get('res.partner').id,
                'action': review_action if business_partner_ids else False,
                'result': 'reviewed' if not business_partner_ids else 'anomaly',
            })

        return checks
