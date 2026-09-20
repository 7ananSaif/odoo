# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models


class L10n_NgTaxReportHandler(models.AbstractModel):
    _name = 'l10n_ng.tax.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = 'Nigerian Tax Report Custom Handler'

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        if warnings is not None and options['date']['period_type'] != 'month':
            warnings['l10n_ng_reports.tax_report_period_check'] = {
                'warning_message': _("Choose a month in the filter to display the VAT report correctly."),
                'alert_type': 'warning',
            }
