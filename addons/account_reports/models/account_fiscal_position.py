from odoo import models


class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    def action_create_foreign_taxes(self):
        # EXTENDS account
        super().action_create_foreign_taxes()
        self.env['account.return.type']._generate_or_refresh_all_returns(self.company_id.root_id)
