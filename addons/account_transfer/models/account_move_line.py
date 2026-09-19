from odoo import _, api, models
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.constrains('tax_ids')
    def _check_auto_transfer_line_ids_tax(self):
        if any(line.move_id.transfer_model_id and line.tax_ids for line in self):
            raise UserError(_("You cannot set Tax on computed Transfer's entries."))
