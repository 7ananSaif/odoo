from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_ma_kilometric_exemption = fields.Monetary(
        string='Kilometric Exemption', groups="hr_payroll.group_hr_payroll_user",
        tracking=True)
    l10n_ma_transport_exemption = fields.Monetary(
        string='Transportation Exemption', groups="hr_payroll.group_hr_payroll_user",
        tracking=True)
    l10n_ma_hra = fields.Monetary(string='HRA', tracking=True, help="House rent allowance.", groups="hr_payroll.group_hr_payroll_user")
    l10n_ma_da = fields.Monetary(string="DA", help="Dearness allowance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ma_meal_allowance = fields.Monetary(string="Meal Allowance", help="Meal allowance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ma_medical_allowance = fields.Monetary(string="Medical Allowance", help="Medical allowance", groups="hr_payroll.group_hr_payroll_user", tracking=True)

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "MA":
            whitelisted_fields += [
                "l10n_ma_da",
                "l10n_ma_hra",
                "l10n_ma_kilometric_exemption",
                "l10n_ma_meal_allowance",
                "l10n_ma_medical_allowance",
                "l10n_ma_transport_exemption",
            ]
        return whitelisted_fields
