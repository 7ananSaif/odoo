# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_it_sdworx_code = fields.Char("SD Worx IT Code", groups="hr_payroll.group_hr_payroll_user")

    @api.constrains('l10n_it_sdworx_code')
    def _check_sdworx_code(self):
        if self.l10n_it_sdworx_code and len(self.l10n_it_sdworx_code) != 7:
            raise ValidationError(self.env._('The SD Worx code should have 7 characters'))
