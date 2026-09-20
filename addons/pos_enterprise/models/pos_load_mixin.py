# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, api


class PosLoadMixin(models.AbstractModel):
    _inherit = "pos.load.mixin"

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return False

    @api.model
    def _load_pos_preparation_data_fields(self):
        return []

    def _load_pos_preparation_data(self, data):
        domain = self._load_pos_preparation_data_domain(data)
        fields = self._load_pos_preparation_data_fields()
        return self.search_read(domain, fields, load=False) if domain is not False else []
