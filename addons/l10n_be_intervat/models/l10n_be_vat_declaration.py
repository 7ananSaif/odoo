from odoo import fields, models


class L10nBeVatDeclaration(models.Model):
    _name = 'l10n_be.vat.declaration'
    _description = "Represents a declaration sent through the Intervat API"

    pdf_ref = fields.Char(readonly=True, required=True)
    xml_ref = fields.Char(readonly=True, required=True)
    declaration_file = fields.Binary(string="ZIP File", readonly=True, required=True)
    rectification_declaration_id = fields.Many2one('l10n_be.vat.declaration', string="Rectification Declaration")
    return_id = fields.Many2one('account.return', string='Return', required=True)
