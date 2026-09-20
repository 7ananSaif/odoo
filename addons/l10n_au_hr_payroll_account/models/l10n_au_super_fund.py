# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10n_AuSuperFund(models.Model):
    _inherit = "l10n_au.super.fund"

    bank_account_id = fields.Many2one(
        "res.partner.bank",
        string="Bank Account",
        compute="_compute_bank_account",
        store="True", readonly=False,
        domain="[('partner_id', '=', address_id)]",
        help="Bank Account to used for Super Payments to SMSF."
    )

    @api.constrains("bank_account_id", "fund_type", "esa", "usi")
    def _check_bank_account_id(self):
        smsf_invalid_records = self.filtered(lambda record: record.fund_type == "SMSF" and not (record.bank_account_id and record.bank_account_id.aba_bsb and record.esa))
        if smsf_invalid_records:
            raise ValidationError(_("Electronic service address and a Bank Account with BSB (Bank State Branch) are required for SMSF type Funds."))
        arpa_invalid_records = self.filtered(lambda record: record.fund_type == "APRA" and not record.usi)
        if arpa_invalid_records:
            raise ValidationError(_("Unique Superannuation Identifier is required for APRA type Funds."))

    @api.depends('address_id', 'address_id.bank_ids')
    def _compute_bank_account(self):
        for rec in self:
            bank_accounts = rec.address_id.sudo().bank_ids
            rec.bank_account_id = bank_accounts[:1]
