from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_ro_work_type = fields.Selection(readonly=False, related="version_id.l10n_ro_work_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
