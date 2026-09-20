# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    official_company_code = fields.Char("Sd worx code", groups="hr.group_hr_user")

    @api.constrains('official_company_code')
    def _check_sdworx_code(self):
        if self.official_company_code and len(self.official_company_code) != 6:
            raise ValidationError(self.env._('Sd worx code should have 6 characters!'))
