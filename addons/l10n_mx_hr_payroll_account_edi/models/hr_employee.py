# Part of Odoo. See LICENSE file for full copyright and licensing details.

from pytz import timezone

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_mx_curp = fields.Char('CURP', groups="hr.group_hr_user", tracking=True)
    l10n_mx_rfc = fields.Char('RFC', groups="hr.group_hr_user", tracking=True)

    @api.constrains('l10n_mx_curp')
    def _check_curp(self):
        for employee in self:
            if employee.l10n_mx_curp and len(employee.l10n_mx_curp) != 18:
                raise ValidationError(self.env._('The CURP must contain 18 characters.'))

    @api.constrains('l10n_mx_rfc')
    def _check_rfc(self):
        for employee in self:
            if employee.l10n_mx_rfc and len(employee.l10n_mx_rfc) != 13:
                raise ValidationError(self.env._('The RFC must contain 13 characters.'))

    def _l10n_mx_edi_get_cfdi_timezone(self):
        self.ensure_one()
        if self.user_partner_id:
            return self.user_partner_id._l10n_mx_edi_get_cfdi_timezone()
        return timezone(self.tz)
