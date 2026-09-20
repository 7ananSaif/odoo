# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_ke_pension_contribution = fields.Monetary("Pension Contribution", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_food_allowance = fields.Monetary("Food Allowance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_airtime_allowance = fields.Monetary("Airtime Allowance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_pension_allowance = fields.Monetary("Pension Allowance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_commuter_allowance = fields.Monetary("Commuter Allowance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_housing_allowance_fixed = fields.Monetary("Housing Allowance Fixed", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_housing_allowance_percentage = fields.Float("Housing Allowance Percentage", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_housing_allowance_unit = fields.Selection(
        selection=[('fixed', '/ month'), ('percentage', 'Percentage')],
        string="Housing Allowance Unit", required=True, default='fixed', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_voluntary_medical_insurance = fields.Monetary("Voluntary Medical Insurance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_life_insurance = fields.Monetary("Life Insurance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_is_li_managed_by_employee = fields.Boolean(
        string="Managed by Employee", groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help="If selected, Life Insurance will be paid by the employee on his own, only the life insurance relief will be deduced from payslip.")
    l10n_ke_education = fields.Monetary("Education", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_is_secondary = fields.Boolean(
        string="Secondary Contract", groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help="Check if the employee got a main contract in another company.")
    l10n_ke_mortgage = fields.Monetary(string="Mortgage Interest", currency_field='currency_id', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_tier_2_remit = fields.Selection(
        selection=[('nssf', 'NSSF'), ('insurance', 'Insurance')], required=True, default='nssf', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ke_pension_remit = fields.Selection(
        selection=[('nssf', 'NSSF'), ('insurance', 'Insurance')], required=True, default='nssf', groups="hr_payroll.group_hr_payroll_user", tracking=True)

    @api.constrains('l10n_ke_mortgage')
    def _check_l10n_ke_mortgage(self):
        max_amount_yearly = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('l10n_ke_max_mortgage', raise_if_not_found=False)
        for version in self:
            if max_amount_yearly and version.l10n_ke_mortgage > max_amount_yearly:
                raise UserError(_('The mortgage interest cannot exceed %s Ksh yearly.', max_amount_yearly))

    @api.constrains('l10n_ke_housing_allowance_percentage')
    def _check_l10n_ke_housing_allowance_percentage(self):
        for version in self:
            if not 0 <= version.l10n_ke_housing_allowance_percentage <= 1:
                raise UserError(_('The housing allowance percentage should be between 0% and 100%.'))

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "KE":
            whitelisted_fields += [
                "l10n_ke_airtime_allowance",
                "l10n_ke_education",
                "l10n_ke_food_allowance",
                "l10n_ke_is_li_managed_by_employee",
                "l10n_ke_is_secondary",
                "l10n_ke_life_insurance",
                "l10n_ke_pension_allowance",
                "l10n_ke_pension_contribution",
                "l10n_ke_voluntary_medical_insurance",
            ]
        return whitelisted_fields
