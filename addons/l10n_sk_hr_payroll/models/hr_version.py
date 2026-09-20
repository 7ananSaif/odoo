from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_sk_meal_voucher_employee = fields.Monetary("Meal Vouchers Amount (Employee)", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_sk_meal_voucher_employer = fields.Monetary("Meal Vouchers Amount (Employer)", groups="hr_payroll.group_hr_payroll_user", tracking=True)

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == 'SK':
            whitelisted_fields += [
                "l10n_sk_meal_voucher_employee",
                "l10n_sk_meal_voucher_employer",
            ]
        return whitelisted_fields
