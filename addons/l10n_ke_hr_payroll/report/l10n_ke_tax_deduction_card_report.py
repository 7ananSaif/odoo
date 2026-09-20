# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ReportL10n_Ke_Hr_PayrollReport_Tax_Deduction_Card(models.AbstractModel):
    _name = 'report.l10n_ke_hr_payroll.report_tax_deduction_card'
    _description = 'Tax Deduction Card Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        return data
