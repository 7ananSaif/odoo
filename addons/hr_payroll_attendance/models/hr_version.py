from odoo import fields, models


class HrVersion(models.Model):
    _inherit = "hr.version"

    ruleset_id = fields.Many2one(groups="hr_payroll.group_hr_payroll_user")
