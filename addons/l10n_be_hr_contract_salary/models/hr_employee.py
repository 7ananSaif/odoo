from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    double_holiday_wage = fields.Monetary(related="version_id.double_holiday_wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_bicyle_cost = fields.Float(related="version_id.l10n_be_bicyle_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_mobility_budget_amount = fields.Monetary(readonly=True)
    l10n_be_wage_with_mobility_budget = fields.Monetary(readonly=True)
