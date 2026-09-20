from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    overtime_from_attendance = fields.Boolean(groups="hr_payroll.group_hr_payroll_user")
    ruleset_id = fields.Many2one(groups="hr_payroll.group_hr_payroll_user")
