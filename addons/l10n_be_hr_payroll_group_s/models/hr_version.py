# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrVersion(models.Model):
    _inherit = 'hr.version'

    group_s_code = fields.Char("Group S code", groups="hr_payroll.group_hr_payroll_user", tracking=True)

    @api.constrains('group_s_code')
    def _check_group_s_code(self):
        if any(version.group_s_code and len(version.group_s_code) != 6 and version.country_code == 'BE' for version in self):
            raise ValidationError(_('The Groups S code should have 6 characters!'))
        similar_group_s_codes = dict(self._read_group(
            domain=[
                ('company_id', 'in', self.company_id.ids),
                ('group_s_code', 'in', self.mapped('group_s_code')),
            ],
            groupby=['group_s_code'],
            aggregates=['employee_id:recordset'],
        ))
        if any(
            similar_group_s_codes.get(version.group_s_code)
            and len(similar_group_s_codes[version.group_s_code]) > 1
            and version.country_code == 'BE'
            and version.group_s_code
            for version in self
        ):
            raise ValidationError(_('The Groups S code should be unique by employee!'))
