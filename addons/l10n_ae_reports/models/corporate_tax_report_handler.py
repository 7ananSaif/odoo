from odoo import models


class L10n_AeCorporateTaxReportHandler(models.AbstractModel):
    _name = 'l10n_ae.corporate.tax.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = "Custom Handler for Corporate TAX Reports in UAE"

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        # Overrides account.report
        company = self.env['res.company'].browse(report.get_report_company_ids(options)[0])
        if not (company.l10n_ae_tax_report_expenses_account and company.l10n_ae_tax_report_liabilities_account and company.l10n_ae_tax_report_asset_account):
            warnings['l10n_ae_reports.corporate_report_accounts_not_configured'] = {}

    def l10n_ae_corporate_tax_report_open_settings(self, options):
        return self.env['ir.actions.act_window']._for_xml_id('account.action_account_config')

    def _report_custom_engine_total_disallowed_expenses(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        lines = self.env['account.fiscal.report.handler']._get_query_results(options, primary_fields=['category_id'])
        return {'balance': sum((next(iter(value.values()))['account_deductible_amount'] or 0) for value in lines.values()) if lines else 0}
