# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_eg_housing_allowance = fields.Monetary(string='Egypt Housing Allowance', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_eg_transportation_allowance = fields.Monetary(string='Egypt Transportation Allowance', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_eg_other_allowances = fields.Monetary(string='Egypt Other Allowances', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_eg_number_of_days = fields.Integer(
        string='Provision number of days', groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help='Number of days of basic salary to be added to the end of service provision per year')
    l10n_eg_total_number_of_days = fields.Integer(
        string='Total Number of Days', groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help='Number of days of basic salary to be added to the end of service benefit')
    l10n_eg_total_eos_benefit = fields.Integer(
        string='Total End of service benefit', groups="hr_payroll.group_hr_payroll_user",
        compute='_compute_end_of_service')
    l10n_eg_social_insurance_reference = fields.Monetary(string='Social Insurance Reference Amount', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_eg_total_leave_days = fields.Float(string='Total Leave Days', default=21, groups="hr_payroll.group_hr_payroll_user", tracking=True)

    @api.depends('l10n_eg_total_number_of_days', 'l10n_eg_other_allowances', 'l10n_eg_transportation_allowance', 'wage')
    def _compute_end_of_service(self):
        for version in self:
            version.l10n_eg_total_eos_benefit = ((version._get_contract_wage() + version.l10n_eg_transportation_allowance + version.l10n_eg_other_allowances) / 30) * version.l10n_eg_total_number_of_days

    _check_l10n_eg_number_of_days_positive = models.Constraint(
        'CHECK(l10n_eg_number_of_days >= 0)',
        "Provision Number of Days must be equal to or greater than 0",
    )
    _check_l10n_eg_total_number_of_days_positive = models.Constraint(
        'CHECK(l10n_eg_total_number_of_days >= 0)',
        "Benefit Number of Days must be equal to or greater than 0",
    )

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "EG":
            whitelisted_fields += [
                "l10n_eg_housing_allowance",
                "l10n_eg_number_of_days",
                "l10n_eg_other_allowances",
                "l10n_eg_social_insurance_reference",
                "l10n_eg_total_leave_days",
                "l10n_eg_total_number_of_days",
                "l10n_eg_transportation_allowance",
            ]
        return whitelisted_fields
