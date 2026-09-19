# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    wise_account_type = fields.Selection([
        ('aba', 'ACH'),
        ('fedwire_local', 'Wire (Fedwire)'),
    ], string="Direct Deposit Transfer Type", default="aba", help="Specify the recipient's preferred transaction type (ACH or Wire) when sending a U.S. Direct Deposit payment. The Transfer type will determine transfer speed, applicable fees, and availability through Wise.")

    wise_bank_account = fields.Char(
        string='Wise Account ID',
        help='ID of the linked account in Wise',
        compute='_compute_wise_bank_account',
        copy=False,
        store=True
    )

    @api.depends('wise_account_type', 'acc_number', 'clearing_number', 'l10n_us_bank_account_type')
    def _compute_wise_bank_account(self):
        for bank in self:
            # Clear the Wise account if the bank details change
            self.wise_bank_account = False
