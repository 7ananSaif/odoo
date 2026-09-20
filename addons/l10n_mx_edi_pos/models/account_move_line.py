from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _compute_account_id(self):
        # EXTENDS 'account
        super()._compute_account_id()
        for line in self:
            if (
                line.move_id.country_code == 'MX'
                and line.move_type == 'out_invoice'
                and line.display_type == 'product'
                and 'closed' in line.move_id.pos_order_ids.session_id.mapped('state')
                and line.company_id.l10n_mx_income_re_invoicing_account_id
            ):
                line.account_id = line.company_id.l10n_mx_income_re_invoicing_account_id
