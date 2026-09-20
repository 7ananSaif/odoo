# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_mx_holiday_bonus_rate = fields.Float(string="MX: Holiday Bonus Rate", groups="hr_payroll.group_hr_payroll_user", tracking=True)

    l10n_mx_payment_period_vouchers = fields.Selection([
        ('last_day_of_month', 'Last Day of the Month'),
        ('in_period', 'In the period'),
    ], default="last_day_of_month", required=True, groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_mx_meal_voucher_amount = fields.Monetary(string="MX: Meal Vouchers", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_mx_transport_amount = fields.Monetary(string="MX: Transport Amount", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_mx_gasoline_amount = fields.Monetary(string="MX: Gasoline Amount", groups="hr_payroll.group_hr_payroll_user", tracking=True)

    l10n_mx_savings_fund = fields.Monetary(string="MX: Savings Fund", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_mx_infonavit = fields.One2many(
        'l10n.mx.hr.infonavit', 'version_id', string="MX: Infonavit", groups="hr.group_hr_user", tracking=True)
    l10n_mx_fonacot = fields.One2many(
        'l10n.mx.hr.fonacot', 'version_id', string="MX: Fonacot", groups="hr.group_hr_user", tracking=True)

    _check_christmas_bonus_percentage = models.Constraint(
         'CHECK (0 <= l10n_mx_holiday_bonus_rate AND l10n_mx_holiday_bonus_rate <= 100)',
         'The Christmas Bonus rate must be between 0 and 100',
    )

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "MX":
            whitelisted_fields += [
                "l10n_mx_fonacot",
                "l10n_mx_gasoline_amount",
                "l10n_mx_holiday_bonus_rate",
                "l10n_mx_infonavit",
                "l10n_mx_meal_voucher_amount",
                "l10n_mx_payment_period_vouchers",
                "l10n_mx_savings_fund",
                "l10n_mx_transport_amount",
            ]
        return whitelisted_fields
