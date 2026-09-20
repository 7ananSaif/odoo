from odoo import fields, models, api


class L10n_Mx_EdiHazardousMaterial(models.Model):
    _name = 'l10n_mx_edi.hazardous.material'
    _description = 'Mexican Hazardous Material'

    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Name', required=True)

    @api.depends('code')
    def _compute_display_name(self):
        for prod in self:
            prod.display_name = f"{prod.code} {prod.name or ''}"
