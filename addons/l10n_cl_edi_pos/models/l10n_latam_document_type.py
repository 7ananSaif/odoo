# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class L10n_LatamDocumentType(models.Model):
    _name = 'l10n_latam.document.type'
    _inherit = ['l10n_latam.document.type', 'pos.load.mixin']

    @api.model
    def _load_pos_data_fields(self, config):
        result = super()._load_pos_data_fields(config)
        if self.env.company.country_id.code == 'CL':
            return ['name']
        return result

    def _load_pos_data_domain(self, data, config):
        result = super()._load_pos_data_domain(data, config)
        if self.env.company.country_id.code == 'CL':
            return False
        return result
