from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    l10n_mx_edi_customs_number = fields.Char(related="lot_id.l10n_mx_edi_customs_number")
