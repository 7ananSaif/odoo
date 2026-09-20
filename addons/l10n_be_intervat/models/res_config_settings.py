from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_be_intervat_ecb = fields.Char(
        string="Intervat VAT number",
        related='company_id.vat',
        readonly=False,
    )
    l10n_be_intervat_mode = fields.Selection(
        related='company_id.l10n_be_intervat_mode',
        readonly=False,
    )
