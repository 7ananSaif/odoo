# coding: utf-8
from odoo import fields, models


class L10n_Co_EdiType_Code(models.Model):
    _name = 'l10n_co_edi.type_code'
    _description = "Colombian EDI Type Code"

    name = fields.Char(required=True)
    description = fields.Char(required=True)
