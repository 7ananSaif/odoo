from odoo import fields, models


class BeCompanyType(models.Model):
    _name = 'l10n_be.company.type'
    _description = "Belgian Company Type"

    name = fields.Char(string="Name", required=True, translate=True)
    xbrl_code = fields.Char(string="XBRL Code", required=True)
