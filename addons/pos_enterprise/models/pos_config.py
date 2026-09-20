# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class PosConfig(models.Model):
    _inherit = 'pos.config'

    module_pos_iot = fields.Boolean('IoT Box', related="is_posbox")
    module_pos_urban_piper = fields.Boolean(string='Is an Urbanpiper')

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        config_ids = data['pos.prep.display'][0]['pos_config_ids']
        return [('id', 'in', config_ids)] if len(config_ids) else []

    @api.model
    def _load_pos_preparation_data_fields(self):
        res = super()._load_pos_preparation_data_fields()
        return res + ['use_presets']
