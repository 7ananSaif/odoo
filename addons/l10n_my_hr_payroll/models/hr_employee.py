from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_my_socso_exempted = fields.Boolean(readonly=False, related="version_id.l10n_my_socso_exempted", inherited=True, groups="hr_payroll.group_hr_payroll_user")
