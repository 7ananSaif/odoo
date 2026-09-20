from odoo import fields, models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    l10n_mx_edi_customs_number = fields.Char(related="lot_id.l10n_mx_edi_customs_number")
