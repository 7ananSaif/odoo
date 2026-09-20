# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class StockPutInPack(models.TransientModel):
    _inherit = 'stock.put.in.pack'

    available_scale_ids = fields.Many2many('iot.device', compute='_compute_available_scale_ids')
    iot_device_id = fields.Many2one('iot.device', "Scale", compute='_compute_iot_device_id', store=True, readonly=False)
    iot_device_identifier = fields.Char(related='iot_device_id.identifier')
    iot_ip = fields.Char(related='iot_device_id.iot_ip')
    manual_measurement = fields.Boolean(related='iot_device_id.manual_measurement')

    @api.depends('move_line_ids', 'package_ids')
    def _compute_available_scale_ids(self):
        for wizard in self:
            move_lines = wizard.move_line_ids
            if wizard.package_ids:
                move_lines = wizard.package_ids.move_line_ids
            wizard.available_scale_ids = move_lines.picking_type_id.iot_scale_ids

    @api.depends('move_line_ids', 'package_ids')
    def _compute_iot_device_id(self):
        for wizard in self:
            move_lines = wizard.move_line_ids
            if wizard.package_ids:
                move_lines = wizard.package_ids.move_line_ids
            picking_type_scales = move_lines.picking_type_id.iot_scale_ids
            if len(picking_type_scales) == 1:
                wizard.iot_device_id = picking_type_scales
