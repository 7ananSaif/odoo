# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_pos_iot_ingenico = fields.Boolean("Ingenico Payment Terminal", help="The transactions are processed by Ingenico via an IoT box. Setup your terminal on the related payment method.")
    module_pos_iot_worldline = fields.Boolean("Worldline Payment Terminal", help="The transactions are processed by Worldline via an IoT box. Setup your terminal on the related payment method.")
    module_pos_iot_six = fields.Boolean("Six Payment Terminal", help="The transactions are processed by Six via an IoT box. Setup your terminal on the related payment method.")

    # pos.config fields
    pos_iface_display_id = fields.Many2one(related='pos_config_id.iface_display_id', readonly=False)
    pos_iface_printer_id = fields.Many2one(related='pos_config_id.iface_printer_id', readonly=False)
    pos_iface_scale_id = fields.Many2one(related='pos_config_id.iface_scale_id', readonly=False)
    pos_iface_scanner_ids = fields.Many2many(related='pos_config_id.iface_scanner_ids', readonly=False)
