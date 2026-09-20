from odoo import api, models


class EventEvent(models.Model):
    _inherit = 'event.event'

    @api.model
    def _load_pos_data_fields(self, config_id):
        return super()._load_pos_data_fields(config_id) + ['badge_format']
