from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    interchange_agreement_id = fields.Char(
        string="Interchange Agreement ID (Destatis)",
        related="company_id.interchange_agreement_id",
        readonly=False,
        help="The identifier assigned by the German Federal Statistical Office for INSTAT/XML declarations.",
    )
