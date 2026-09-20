# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_jo_housing_allowance = fields.Monetary(string='Jordan Housing Allowance', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_jo_transportation_allowance = fields.Monetary(string='Jordan Transportation Allowance', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_jo_other_allowances = fields.Monetary(string='Jordan Other Allowances', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_jo_tax_exemption = fields.Monetary(string='Jordan Tax Exemption Amount', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_jo_number_of_leave_days = fields.Float(default=14, string='Jordan Number of Leave Days', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_jo_is_commission_based = fields.Boolean(string='Is Commission based', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_jo_is_blind = fields.Boolean(string="Is Blind", groups="hr_payroll.group_hr_payroll_user",
        help="Used to determine if the employee qualifies for the annual disability tax exemption due to blindness.", tracking=True)
    l10n_jo_has_dependants = fields.Boolean(string="Has Dependants", groups="hr_payroll.group_hr_payroll_user",
        help="Used to determine if the employee qualifies for dependent-related tax exemptions (e.g., spouse, children).", tracking=True)
    l10n_jo_is_eligible_for_eos = fields.Boolean(default=True, groups="hr_payroll.group_hr_payroll_user", string="Eligible for EOS", tracking=True)

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "JO":
            whitelisted_fields += [
                "l10n_jo_housing_allowance",
                "l10n_jo_other_allowances",
                "l10n_jo_tax_exemption",
                "l10n_jo_transportation_allowance",
            ]
        return whitelisted_fields
