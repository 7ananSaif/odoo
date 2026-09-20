from odoo import fields, models


class AccountMoveLine(models.Model):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    # Technical field to link a payment that is used in a batch without entries
    payment_lines_ids = fields.Many2many(comodel_name='account.payment')
