# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = "hr.version"

    l10n_ae_housing_allowance = fields.Monetary(string="Housing Allowance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ae_transportation_allowance = fields.Monetary(string="Transportation Allowance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ae_other_allowances = fields.Monetary(string="Other Allowances", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ae_total_salary = fields.Monetary(string="Total Salary", groups="hr_payroll.group_hr_payroll_user",
                                           compute="_compute_total_salary", help="Used in salary rules and on printouts")
    l10n_ae_is_dews_applied = fields.Boolean(string="Is DEWS Applied", groups="hr_payroll.group_hr_payroll_user",
                                             help="Daman Investments End of Service Programme", tracking=True)
    l10n_ae_number_of_leave_days = fields.Integer(string="Number of Leave Days", default=30, groups="hr_payroll.group_hr_payroll_user", tracking=True,
                                                  help="Number of leave days of gross salary to be added to the annual leave provision per month")
    l10n_ae_is_computed_based_on_daily_salary = fields.Boolean(string="Computed Based On Daily Salary", groups="hr_payroll.group_hr_payroll_user", tracking=True,
                                                               help="If True, The EOS will be computed based on the daily salary provided rather than the basic salary")
    l10n_ae_eos_daily_salary = fields.Float(string="Daily Salary", groups="hr_payroll.group_hr_payroll_user", tracking=True)

    _l10n_ae_hr_payroll_number_of_leave_days_constraint = models.Constraint(
        'CHECK(l10n_ae_number_of_leave_days >= 0)',
        "Number of Leave Days must be equal to or greater than 0",
    )

    @api.depends('wage', 'l10n_ae_housing_allowance', 'l10n_ae_transportation_allowance', 'l10n_ae_other_allowances')
    def _compute_total_salary(self):
        for contract in self:
            contract.l10n_ae_total_salary = contract.wage + contract.l10n_ae_housing_allowance + contract.l10n_ae_transportation_allowance + contract.l10n_ae_other_allowances

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template()
        if self.env.company.country_id.code == "AE":
            whitelisted_fields += [
                "l10n_ae_eos_daily_salary",
                "l10n_ae_housing_allowance",
                "l10n_ae_is_computed_based_on_daily_salary",
                "l10n_ae_is_dews_applied",
                "l10n_ae_number_of_leave_days",
                "l10n_ae_other_allowances",
                "l10n_ae_transportation_allowance",
            ]
        return whitelisted_fields
