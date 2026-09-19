from odoo import models, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _load_pos_data_fields(self, config):
        params = super()._load_pos_data_fields(config)
        params += ['street2']
        return params
