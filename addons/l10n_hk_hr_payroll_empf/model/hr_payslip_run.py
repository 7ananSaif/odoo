# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.fields import Domain


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    # ------------------
    # Fields declaration
    # ------------------

    l10n_hk_payroll_scheme_id = fields.Many2one(
        string="MPF Scheme",
        help="If set, employees in this Pay Run will be filtered to the selected scheme and a eMPF report will be automatically generated once the pay run is validated.",
        comodel_name="l10n_hk.mpf.scheme",
        domain="[('employer_account_number', '!=', False)]",
    )
    l10n_hk_payroll_group_id = fields.Many2one(
        string="Payroll Group",
        help="If set, employees in this Pay Run will be filtered to the selected group and a eMPF report will be automatically generated once the pay run is validated.",
        comodel_name="l10n_hk.payroll.group",
        domain="[('company_id', '=', company_id), ('scheme_id', '=', l10n_hk_payroll_scheme_id)]",
    )
    # Technical field
    l10n_hk_payroll_empf_report_id = fields.One2many(
        comodel_name='l10n_hk.empf.contribution.report',
        inverse_name='payslip_run_id',
        domain="[('company_id', '=', company_id)]",
        export_string_translation=False,
    )

    # --------------
    # Action methods
    # --------------

    def action_l10n_hk_hr_version_list_view_payrun(self, date_start=None, date_end=None, structure_id=None, company_id=None, schedule_pay=None, payroll_group_id=None, payroll_scheme_id=None):
        """ Add the functionality to receive a payroll group id from the front-end, and to use it to filter the available employees. """
        action = self.action_payroll_hr_version_list_view_payrun(date_start, date_end, structure_id, company_id, schedule_pay)
        # Get the ids matching the other settings, and filter them further to only show the ones with the selected group, if any.
        payroll_scheme_id = (payroll_scheme_id or self.l10n_hk_payroll_scheme_id.id)
        payroll_group_id = (payroll_group_id or self.l10n_hk_payroll_group_id.id)
        if not payroll_scheme_id and not payroll_group_id:
            return action

        domain = Domain(Domain.TRUE)
        if payroll_group_id:
            domain = Domain('l10n_hk_payroll_group_id', '=', payroll_group_id)
        elif payroll_scheme_id:
            domain = Domain('l10n_hk_mpf_scheme_id', '=', payroll_scheme_id)

        version_ids = action['domain'][0][2]
        versions = self.env['hr.version'].browse(version_ids).filtered_domain(domain)
        action['domain'] = [('id', 'in', versions.ids)]
        return action

    def action_validate(self):
        """
        When validating a Pay Run, we can generate a eMPF report for it.
        This will give a head start to the Payroll team when it is time to send it.
        """
        super().action_validate()
        hk_payrun = self.filtered(lambda p: p.country_code == 'HK' and (p.l10n_hk_payroll_scheme_id or p.l10n_hk_payroll_group_id))
        if not hk_payrun:
            return

        empf_contribution_reports_data = []
        # For payruns that already have reports (set to draft and reconfirmed/...) we only recompute the lines.
        payruns_with_reports = hk_payrun.filtered('l10n_hk_payroll_empf_report_id')
        for report in payruns_with_reports.l10n_hk_payroll_empf_report_id:
            report._create_contribution_lines()
        for payrun in (hk_payrun - payruns_with_reports):
            empf_contribution_reports_data.append({
                'payslip_run_id': payrun.id,
                'company_id': payrun.company_id.id,
            })
        self.env['l10n_hk.empf.contribution.report'].create(empf_contribution_reports_data)

    def action_open_empf_contribution_report(self):
        self.ensure_one()
        return self.l10n_hk_payroll_empf_report_id._get_records_action()

    # ----------------
    # Business methods
    # ----------------

    def _get_valid_version_ids(self, date_start=None, date_end=None, structure_id=None, company_id=None, employee_ids=None, schedule_pay=None):
        """ Update the method to additionally filter on the group/scheme if set. """
        valid_version_ids = super()._get_valid_version_ids(date_start, date_end, structure_id, company_id, employee_ids, schedule_pay)
        if not self.l10n_hk_payroll_scheme_id and not self.l10n_hk_payroll_group_id:
            return valid_version_ids

        domain = Domain(Domain.TRUE)
        if self.l10n_hk_payroll_group_id:
            domain = Domain('l10n_hk_payroll_group_id', '=', self.l10n_hk_payroll_group_id.id)
        elif self.l10n_hk_payroll_scheme_id:
            domain = Domain('l10n_hk_mpf_scheme_id', '=', self.l10n_hk_payroll_scheme_id.id)

        versions = self.env['hr.version'].browse(valid_version_ids).filtered_domain(domain)
        return versions.ids
