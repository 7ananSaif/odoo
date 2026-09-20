# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Employee(models.Model):
    _inherit = 'hr.employee'

    l10n_eg_housing_allowance = fields.Monetary(readonly=False, related="version_id.l10n_eg_housing_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_eg_transportation_allowance = fields.Monetary(readonly=False, related="version_id.l10n_eg_transportation_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_eg_other_allowances = fields.Monetary(readonly=False, related="version_id.l10n_eg_other_allowances", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_eg_number_of_days = fields.Integer(readonly=False, related="version_id.l10n_eg_number_of_days", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_eg_total_number_of_days = fields.Integer(readonly=False, related="version_id.l10n_eg_total_number_of_days", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_eg_total_eos_benefit = fields.Integer(readonly=False, related="version_id.l10n_eg_total_eos_benefit", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_eg_social_insurance_reference = fields.Monetary(readonly=False, related="version_id.l10n_eg_social_insurance_reference", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_eg_total_leave_days = fields.Float(readonly=False, related="version_id.l10n_eg_total_leave_days", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    def _l10n_eg_get_annual_remaining_leaves(self):
        result = {}
        allocation_data = self.company_id.l10n_eg_annual_leave_type_id.get_allocation_data(self)
        for employee in self:
            employee_data = allocation_data.get(employee, [])
            if employee_data:
                result[employee.id] = employee_data[0][1]['remaining_leaves']
            else:
                result[employee.id] = 0
        return result
