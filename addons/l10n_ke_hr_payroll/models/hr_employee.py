from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_ke_kra_pin = fields.Char(string="KRA PIN", help="KRA PIN provided by the KRA", groups="hr.group_hr_user")
    l10n_ke_nssf_number = fields.Char(string="NSSF Number", help="NSSF Number provided by the NSSF", groups="hr.group_hr_user")
    l10n_ke_nhif_number = fields.Char("NHIF Number", groups="hr.group_hr_user")
    l10n_ke_shif_number = fields.Char("SHIF Number", groups="hr.group_hr_user")
    l10n_ke_helb_number = fields.Char(string="HELB Number", groups="hr.group_hr_user")
    l10n_ke_pension_contribution = fields.Monetary(readonly=False, related="version_id.l10n_ke_pension_contribution", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ke_food_allowance = fields.Monetary(readonly=False, related="version_id.l10n_ke_food_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ke_airtime_allowance = fields.Monetary(readonly=False, related="version_id.l10n_ke_airtime_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ke_pension_allowance = fields.Monetary(readonly=False, related="version_id.l10n_ke_pension_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ke_voluntary_medical_insurance = fields.Monetary(readonly=False, related="version_id.l10n_ke_voluntary_medical_insurance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ke_life_insurance = fields.Monetary(readonly=False, related="version_id.l10n_ke_life_insurance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ke_is_li_managed_by_employee = fields.Boolean(readonly=False, related="version_id.l10n_ke_is_li_managed_by_employee", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ke_education = fields.Monetary(readonly=False, related="version_id.l10n_ke_education", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ke_is_secondary = fields.Boolean(readonly=False, related="version_id.l10n_ke_is_secondary", inherited=True, groups="hr_payroll.group_hr_payroll_user")
