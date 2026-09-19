# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class L10n_AuSuperFund(models.Model):
    _name = 'l10n_au.super.fund'
    _description = "Super Fund"
    _inherit = ["mail.thread"]
    _rec_names_search = ["name", "abn", "usi"]

    name = fields.Char(string="Name", required=True, tracking=True)
    abn = fields.Char(string="ABN", required=True, tracking=True)
    address_id = fields.Many2one("res.partner", string="Address", required=True, tracking=True)
    fund_type = fields.Selection([
        ("APRA", "APRA"),
        ("SMSF", "SMSF"),
    ], default="APRA", string="Type", required=True)
    usi = fields.Char(string="USI", help="Unique Superannuation Identifier", tracking=True)
    esa = fields.Char(string="ESA", help="Electronic Service Address", tracking=True)
