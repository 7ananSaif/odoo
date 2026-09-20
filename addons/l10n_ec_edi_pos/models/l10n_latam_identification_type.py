from odoo import models, api


class L10n_LatamIdentificationType(models.Model):
    _name = 'l10n_latam.identification.type'
    _inherit = ['l10n_latam.identification.type', 'pos.load.mixin']

    @api.model
    def _load_pos_data_fields(self, config):
        result = super()._load_pos_data_fields(config)
        if self.env.company.country_id.code == 'EC':
            return ['name']
        return result
