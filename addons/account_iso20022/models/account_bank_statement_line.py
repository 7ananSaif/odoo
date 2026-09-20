from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    end_to_end_uuid = fields.Char(
        string='End to End ID',
        help='Unique end-to-end assigned by the initiating party',
    )
