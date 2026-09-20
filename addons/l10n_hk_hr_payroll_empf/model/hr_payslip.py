# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # ------------------
    # Fields declaration
    # ------------------

    # Technical fields
    l10n_hk_contribution_line_id = fields.One2many(
        comodel_name='l10n_hk.empf.contribution.report.line',
        inverse_name='payslip_id',
        export_string_translation=False,
    )
    l10n_hk_version_scheme_id = fields.Many2one(
        related='version_id.l10n_hk_mpf_scheme_id',
        export_string_translation=False,
    )

    def _l10n_hk_filter_slips_requiring_reporting(self):
        """
        Helper that returns the payslips in self that requires to appear in the contribution report.
        In practice, ALL payslips for employees that are in age of contributing should return True, exceptions being:
        - Payslips for employees younger than 16 (although I believe this shouldn't happen)
        - Payslips for employees that are older than 65 and that are not using VC
        - Payslips for employees that are exempt of MPF and are not using VC
        Some payslips without contributions need to be returned (we rely on of them for new register for example)
        """
        slips_to_report = self.env['hr.payslip']
        contribution_codes = ['EEMC', 'ERMC', 'EEVC', 'ERVC', 'ERVC2']
        payslip_values = self._get_line_values(contribution_codes)
        for slip in self:
            employee = slip.employee_id
            version = slip.version_id

            is_contributing = any(payslip_values[code][slip.id]['total'] for code in contribution_codes)
            is_of_age = not employee.birthday or employee.birthday < fields.Date.context_today(slip) - relativedelta(years=16)
            is_below_65 = not employee.birthday or employee.birthday > fields.Date.context_today(slip) - relativedelta(years=65)

            if is_of_age and (is_below_65 or (not is_below_65 and is_contributing)) and (not version.l10n_hk_mpf_exempt or (version.l10n_hk_mpf_exempt and is_contributing)):
                slips_to_report |= slip

        return slips_to_report

    # --------------
    # Action methods
    # --------------

    def action_payslip_cancel(self):
        """
        Allowing to cancel payslips that have been reported could lead to inconsistencies.
        Users should reset the report to draft before doing so, so that re-validation is required before submitting the
        report.
        """
        if any(report.state == 'validated' for report in self.l10n_hk_contribution_line_id.report_id):
            raise UserError(self.env._("Payslips that have been included in a validated eMPF report cannot be cancelled. Please first reset the eMPF report to draft."))
        self.l10n_hk_contribution_line_id.filtered(lambda c: c.report_id.state == 'draft').unlink()
        return super().action_payslip_cancel()

    def action_payslip_draft(self):
        """
        Allowing to reset to draft payslips that have been reported could lead to inconsistencies.
        Users should reset the report to draft before doing so, so that re-validation is required before submitting the
        report.
        """
        if any(report.state == 'validated' for report in self.l10n_hk_contribution_line_id.report_id):
            raise UserError(self.env._("Payslips that have been included in a validated eMPF report cannot be reset to draft. Please first reset the eMPF report to draft."))
        self.l10n_hk_contribution_line_id.filtered(lambda c: c.report_id.state == 'draft').unlink()
        return super().action_payslip_draft()
