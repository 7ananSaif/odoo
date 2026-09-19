from odoo import models, api


class PosCategory(models.Model):
    _inherit = "pos.category"

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        categ_ids = data['pos.prep.display'][0]['category_ids']
        return [('id', 'in', categ_ids)] if len(categ_ids) else []

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['display_name']
