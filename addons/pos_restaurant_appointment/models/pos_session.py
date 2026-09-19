# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data_models(self, config):
        data = super()._load_pos_data_models(config)
        if self.config_id.module_pos_restaurant:
            data.remove('calendar.event')
            data += ['appointment.resource', 'calendar.event']
        return data
