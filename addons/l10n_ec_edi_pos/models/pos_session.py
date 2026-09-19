from odoo import api, models


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data_models(self, config):
        data = super()._load_pos_data_models(config)
        if self.env.company.country_id.code == 'EC':
            data += ['l10n_latam.identification.type', 'account.move']
        return data
