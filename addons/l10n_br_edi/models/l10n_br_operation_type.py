# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class L10n_BrOperationType(models.Model):
    _inherit = 'l10n_br.operation.type'

    l10n_br_cfop_code = fields.Char(
        string="CFOP",
        help="Brazil: Use this field to indicate a specific 'CFOP' for this operation. "
             "When this field is set, Avalara will use this CFOP number to issue the e-invoice. "
             "If this field is not set, Avalara will automatically provide the closest CFOP "
             "for the operation that is being used.",
    )

    @api.constrains("l10n_br_cfop_code")
    def _check_l10n_br_cfop_code(self):
        """ Specified by the Avalara API to be a JSON number. We don't do an Integer field to stay more flexible
        in case the government or Avalara decides to suddenly change it. """
        for operation_type in self:
            try:
                int(operation_type.l10n_br_cfop_code)
            except ValueError:
                raise ValidationError(_("The CFOP code on %(operation_type)s must only contain digits (0-9).", operation_type=operation_type.display_name))
