# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_sa_employee_code = fields.Char(string="Saudi National / IQAMA ID", groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_remaining_annual_leave_balance = fields.Float(compute="_compute_l10n_sa_remaining_annual_leave_balance",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_leaves_count_compensable = fields.Float(store=False, groups="hr.group_hr_user")  # to remove in master

    l10n_sa_housing_allowance = fields.Monetary(readonly=False, related="version_id.l10n_sa_housing_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_transportation_allowance = fields.Monetary(readonly=False, related="version_id.l10n_sa_transportation_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_other_allowances = fields.Monetary(readonly=False, related="version_id.l10n_sa_other_allowances", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_number_of_days = fields.Integer(readonly=False, related="version_id.l10n_sa_number_of_days", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_wps_description = fields.Char(readonly=False, related="version_id.l10n_sa_wps_description", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    def _compute_l10n_sa_remaining_annual_leave_balance(self):
        emp_per_company = self.grouped('company_id')
        annual_leave_type_allocation_data = ({
            company.id: company.l10n_sa_annual_leave_type_id.get_allocation_data(emp_per_company[company])
                for company in self.company_id
                if company.l10n_sa_annual_leave_type_id
        })
        for employee in self:
            company_data = annual_leave_type_allocation_data.get(employee.company_id.id, {})
            employee_allocation_data = company_data.get(employee, False)
            employee.l10n_sa_remaining_annual_leave_balance = employee_allocation_data[0][1]['remaining_leaves'] \
                if employee_allocation_data else 0
