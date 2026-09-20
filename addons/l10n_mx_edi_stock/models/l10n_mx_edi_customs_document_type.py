from odoo import fields, models


class L10n_Mx_EdiCustomsDocumentType(models.Model):
    _name = 'l10n_mx_edi.customs.document.type'
    _description = 'Mexican Customs Document Type'

    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Name', required=True)
    goods_direction = fields.Selection(
        selection=[
            ('import', 'Import'),
            ('export', 'Export'),
            ('both', 'Import, Export'),
        ],
        string='Type',
        required=True,
    )

    _uniq_code = models.Constraint(
        'UNIQUE(code)',
        "This code is already used.",
    )
