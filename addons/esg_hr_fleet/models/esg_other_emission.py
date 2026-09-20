from odoo import fields, models


class EsgOtherEmission(models.Model):
    _inherit = "esg.other.emission"

    is_fleet = fields.Boolean(default=False, readonly=True)
