from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _load_pos_data_models(self, config):
        data = super()._load_pos_data_models(config)
        data += ['l10n_ke_edi_oscu.code', 'product.unspsc.code']
        return data
