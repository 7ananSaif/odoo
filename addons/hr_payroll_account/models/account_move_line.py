from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    employee_bank_account_id = fields.Many2one('res.partner.bank', required=False)
