# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    l10n_it_sdworx_code = fields.Char("SD Worx IT Code", groups="hr.group_hr_user")

    @api.constrains('l10n_it_sdworx_code')
    def _check_sdworx_code(self):
        if self.l10n_it_sdworx_code and len(self.l10n_it_sdworx_code) > 3:
            raise ValidationError(self.env._('The SD Worx code must contain at least three characters!'))
