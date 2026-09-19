from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_nl_30_percent = fields.Boolean(readonly=False, related="version_id.l10n_nl_30_percent", inherited=True, groups="hr_payroll.group_hr_payroll_user")
