# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_jo_housing_allowance = fields.Monetary(readonly=False, related="version_id.l10n_jo_housing_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_jo_transportation_allowance = fields.Monetary(readonly=False, related="version_id.l10n_jo_transportation_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_jo_other_allowances = fields.Monetary(readonly=False, related="version_id.l10n_jo_other_allowances", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_jo_tax_exemption = fields.Monetary(readonly=False, related="version_id.l10n_jo_tax_exemption", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_jo_number_of_leave_days = fields.Float(readonly=False, related="version_id.l10n_jo_number_of_leave_days", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_jo_is_commission_based = fields.Boolean(readonly=False, related="version_id.l10n_jo_is_commission_based", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_jo_is_blind = fields.Boolean(readonly=False, related="version_id.l10n_jo_is_blind", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_jo_has_dependants = fields.Boolean(readonly=False, related="version_id.l10n_jo_has_dependants", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_jo_is_eligible_for_eos = fields.Boolean(readonly=False, related="version_id.l10n_jo_is_eligible_for_eos", inherited=True, groups="hr_payroll.group_hr_payroll_user")
