# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_mx_pos_account_income_re_invoicing_id = fields.Many2one(
        comodel_name='account.account',
        string="Income Re-Invoicing Account",
        readonly=False,
        related='company_id.l10n_mx_income_re_invoicing_account_id',
        domain="[('account_type', 'in', ('income', 'expense'))]",
    )
