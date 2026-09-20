# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_ch_lpp_in_percentage = fields.Boolean(readonly=False, related="version_id.l10n_ch_lpp_in_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_lpp_percentage_employee = fields.Float(readonly=False, related="version_id.l10n_ch_lpp_percentage_employee", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_lpp_percentage_employer = fields.Float(readonly=False, related="version_id.l10n_ch_lpp_percentage_employer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_telework_percentage = fields.Float(readonly=False, related="version_id.l10n_ch_telework_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
