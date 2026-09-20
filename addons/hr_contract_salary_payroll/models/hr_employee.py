# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    wage_with_holidays = fields.Monetary(groups="hr_payroll.group_hr_payroll_user")
    wage_on_signature = fields.Monetary(groups="hr_payroll.group_hr_payroll_user")
    final_yearly_costs = fields.Monetary(groups="hr_payroll.group_hr_payroll_user")
    monthly_yearly_costs = fields.Monetary(groups="hr_payroll.group_hr_payroll_user")

    def _get_offer_values(self):
        self.ensure_one()
        vals = super()._get_offer_values()
        monthly_wage = self.version_id._get_gross_from_employer_costs(self.version_id.final_yearly_costs)
        vals.update({
            'monthly_wage': monthly_wage
        })
        return vals
