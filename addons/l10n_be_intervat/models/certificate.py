import secrets

from odoo import fields, models


class Certificate(models.Model):
    _inherit = 'certificate.certificate'

    l10n_be_intervat_jwk_kid = fields.Char(default=lambda self: secrets.token_hex(16), readonly=True)
    l10n_be_intervat_jwk_token = fields.Char(default=lambda self: secrets.token_hex(16), readonly=True)
