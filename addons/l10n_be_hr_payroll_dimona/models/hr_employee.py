# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # YTI TODO Drop those 3 fields in master
    l10n_be_dimona_in_declaration_number = fields.Char(readonly=False, related="version_id.l10n_be_dimona_in_declaration_number", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_last_declaration_number = fields.Char(readonly=False, related="version_id.l10n_be_dimona_last_declaration_number", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_declaration_state = fields.Selection(readonly=False, related="version_id.l10n_be_dimona_declaration_state", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    l10n_be_dimona_planned_hours = fields.Integer(readonly=False, related="version_id.l10n_be_dimona_planned_hours", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_is_student = fields.Boolean(related="version_id.l10n_be_is_student", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    def action_check_dimona(self):
        self.ensure_one()
        return self.version_id.action_check_dimona()

    def _get_split_name(self):
        self.ensure_one()
        names = re.sub(r"\([^()]*\)", "", self.name).strip().split()
        first_name = names[-1]
        last_name = ' '.join(names[:-1])
        return first_name, last_name
