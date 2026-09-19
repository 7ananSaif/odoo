from odoo import models, api


class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model
    def _load_pos_preparation_data_fields(self):
        res = super()._load_pos_preparation_data_fields()
        return res + ['name', 'has_paper']
