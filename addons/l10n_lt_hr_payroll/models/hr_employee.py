from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_lt_benefits_in_kind = fields.Monetary(readonly=False, related="version_id.l10n_lt_benefits_in_kind", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_lt_time_limited = fields.Boolean(readonly=False, related="version_id.l10n_lt_time_limited", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_lt_pension = fields.Boolean(readonly=False, related="version_id.l10n_lt_pension", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_lt_working_capacity = fields.Selection(readonly=False, related="version_id.l10n_lt_working_capacity", inherited=True, groups="hr_payroll.group_hr_payroll_user")
