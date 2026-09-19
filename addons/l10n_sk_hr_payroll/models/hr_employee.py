from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_sk_meal_voucher_employee = fields.Monetary(readonly=False, related="version_id.l10n_sk_meal_voucher_employee", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sk_meal_voucher_employer = fields.Monetary(readonly=False, related="version_id.l10n_sk_meal_voucher_employer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
