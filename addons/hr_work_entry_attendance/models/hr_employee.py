from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    overtime_from_attendance = fields.Boolean(
        readonly=False,
        related="version_id.overtime_from_attendance",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user"
    )
