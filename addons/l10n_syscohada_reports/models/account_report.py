from odoo import fields, models


class AccountReport(models.Model):
    _inherit = 'account.report'

    availability_condition = fields.Selection(selection_add=[('coa_children', "Children of the Chart of Accounts")])

    def _is_available_for(self, options):
        reports = super()._is_available_for(options)

        reports_available_by_coa_children = self.filtered(lambda r: r.availability_condition == 'coa_children')
        if reports_available_by_coa_children:
            companies = self.env['res.company'].browse(self.get_report_company_ids(options))
            chart_templates = {
                parent
                for code in companies.mapped('chart_template')
                for parent in self.env['account.chart.template']._get_parent_template(code)
            }
            reports += reports_available_by_coa_children.filtered(lambda r: r.chart_template in chart_templates)

        return reports

    def _compute_is_account_coverage_report_available(self):
        coa_children_reports = self.filtered(lambda report: report.availability_condition == 'coa_children')
        super(AccountReport, (self - coa_children_reports))._compute_is_account_coverage_report_available()

        if coa_children_reports:
            all_code_available = set(self.env['account.chart.template']._get_parent_template(self.env.company.chart_template))
            for report in coa_children_reports:
                report.is_account_coverage_report_available = self.chart_template in all_code_available
