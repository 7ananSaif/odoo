# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import format_list


class HrVersion(models.Model):
    _inherit = 'hr.version'

    acerta_code = fields.Char("Acerta code", groups="hr_payroll.group_hr_payroll_user")

    @api.constrains('acerta_code')
    def _check_acerta_code(self):
        problematic_versions = self.env['hr.version']
        for version in self:
            if version.acerta_code and len(version.acerta_code) != 20:
                if len(version.acerta_code) > 20:
                    problematic_versions |= version
                version.acerta_code = version.acerta_code.zfill(20)

        if problematic_versions:
            raise ValueError(self.env._(
                "The following versions have an Acerta code that is too long: %(versions)s",
                versions=format_list(self.env, problematic_versions.mapped('name'))
            ))
