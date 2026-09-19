# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    iot_device_id = fields.Many2one('iot.device', string='Payment Terminal Device')

    @api.onchange('use_payment_terminal')
    def _onchange_use_payment_terminal(self):
        super()._onchange_use_payment_terminal()
        self.iot_device_id = False

    @api.model
    def _load_pos_data_fields(self, config):
        result = super()._load_pos_data_fields(config)
        result += ['iot_device_id']
        return result
