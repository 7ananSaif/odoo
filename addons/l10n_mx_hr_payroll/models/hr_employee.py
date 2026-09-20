from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_mx_holiday_bonus_rate = fields.Float(readonly=False, related="version_id.l10n_mx_holiday_bonus_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_mx_payment_period_vouchers = fields.Selection(readonly=False, related="version_id.l10n_mx_payment_period_vouchers", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_mx_meal_voucher_amount = fields.Monetary(readonly=False, related="version_id.l10n_mx_meal_voucher_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_mx_transport_amount = fields.Monetary(readonly=False, related="version_id.l10n_mx_transport_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_mx_gasoline_amount = fields.Monetary(readonly=False, related="version_id.l10n_mx_gasoline_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_mx_savings_fund = fields.Monetary(readonly=False, related="version_id.l10n_mx_savings_fund", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    @api.constrains('bank_account_ids')
    def _check_single_bank_account_mx(self):
        for employee in self:
            if employee.country_code == 'MX' and len(employee.bank_account_ids) > 1:
                raise ValidationError(self.env._("Only one bank account is allowed per employee."))
