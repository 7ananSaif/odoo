# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

STATES = ['NY', 'CA', 'AL', 'CO', 'VT', 'IL', 'AZ', 'DC', 'NC', 'VA', 'OR', 'ID']


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_us_old_w4 = fields.Boolean(readonly=False, related="version_id.l10n_us_old_w4", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_w4_step_2 = fields.Boolean(readonly=False, related="version_id.l10n_us_w4_step_2", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_w4_step_3 = fields.Float(readonly=False, related="version_id.l10n_us_w4_step_3", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_w4_step_4a = fields.Float(readonly=False, related="version_id.l10n_us_w4_step_4a", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_w4_step_4b = fields.Float(readonly=False, related="version_id.l10n_us_w4_step_4b", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_w4_step_4c = fields.Float(readonly=False, related="version_id.l10n_us_w4_step_4c", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_w4_allowances_count = fields.Integer(readonly=False, related="version_id.l10n_us_w4_allowances_count", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_w4_withholding_deduction_allowances = fields.Integer(readonly=False, related="version_id.l10n_us_w4_withholding_deduction_allowances", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_filing_status = fields.Selection(readonly=False, related="version_id.l10n_us_filing_status", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_state_filing_status = fields.Selection(readonly=False, related="version_id.l10n_us_state_filing_status", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_statutory_employee = fields.Boolean(readonly=False, related="version_id.l10n_us_statutory_employee", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_retirement_plan = fields.Boolean(readonly=False, related="version_id.l10n_us_retirement_plan", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_third_party_sick_pay = fields.Boolean(readonly=False, related="version_id.l10n_us_third_party_sick_pay", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_state_withholding_allowance = fields.Float(readonly=False, related="version_id.l10n_us_state_withholding_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_state_extra_withholding = fields.Float(readonly=False, related="version_id.l10n_us_state_extra_withholding", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_pre_retirement_amount = fields.Float(readonly=False, related="version_id.l10n_us_pre_retirement_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_pre_retirement_type = fields.Selection(readonly=False, related="version_id.l10n_us_pre_retirement_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_pre_retirement_matching_amount = fields.Float(readonly=False, related="version_id.l10n_us_pre_retirement_matching_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_pre_retirement_matching_type = fields.Selection(readonly=False, related="version_id.l10n_us_pre_retirement_matching_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_pre_retirement_matching_yearly_cap = fields.Float(readonly=False, related="version_id.l10n_us_pre_retirement_matching_yearly_cap", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_health_benefits_medical = fields.Monetary(readonly=False, related="version_id.l10n_us_health_benefits_medical", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_health_benefits_dental = fields.Monetary(readonly=False, related="version_id.l10n_us_health_benefits_dental", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_health_benefits_vision = fields.Monetary(readonly=False, related="version_id.l10n_us_health_benefits_vision", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_health_benefits_fsa = fields.Monetary(readonly=False, related="version_id.l10n_us_health_benefits_fsa", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_health_benefits_fsadc = fields.Monetary(readonly=False, related="version_id.l10n_us_health_benefits_fsadc", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_health_benefits_hsa = fields.Monetary(readonly=False, related="version_id.l10n_us_health_benefits_hsa", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_commuter_benefits = fields.Monetary(readonly=False, related="version_id.l10n_us_commuter_benefits", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_post_roth_401k_amount = fields.Float(readonly=False, related="version_id.l10n_us_post_roth_401k_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_post_roth_401k_type = fields.Selection(readonly=False, related="version_id.l10n_us_post_roth_401k_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_employee_state_code = fields.Char(related="version_id.l10n_us_employee_state_code", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_us_worker_compensation_id = fields.Many2one(readonly=False, related="version_id.l10n_us_worker_compensation_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
