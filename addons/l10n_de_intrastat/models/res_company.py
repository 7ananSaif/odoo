from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    interchange_agreement_id = fields.Char(
        string="Interchange Agreement ID (Destatis)",
        size=14,
    )
