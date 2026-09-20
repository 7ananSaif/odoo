from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    group_s_code = fields.Char(readonly=False, related="version_id.group_s_code", groups="hr_payroll.group_hr_payroll_user")
