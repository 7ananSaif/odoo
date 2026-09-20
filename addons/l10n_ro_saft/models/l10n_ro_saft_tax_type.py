from odoo import fields, models, api


class L10n_Ro_SaftTaxType(models.Model):
    _name = 'l10n_ro_saft.tax.type'
    _description = 'Romanian SAF-T Tax Type'
    _rec_names_search = ['code', 'description']

    code = fields.Char('Code', required=True)
    description = fields.Char('Description', required=True, translate=True)

    _code_unique = models.Constraint(
        'unique (code)',
        "The code of the tax type must be unique !",
    )

    @api.depends('code', 'description')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f'{record.code} {record.description}'
