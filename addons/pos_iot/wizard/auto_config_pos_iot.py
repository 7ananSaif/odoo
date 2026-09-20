from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)

class AutoConfigPoSIoT(models.TransientModel):
    _name = 'auto.config.pos.iot'
    _description = 'Configure Automatically IoT Box In PoS'

    pos_config_ids = fields.Many2many(
        'pos.config', string="Associated PoS", required=True, default=lambda self: self._get_default_pos()
    )
    iot_box_identifier = fields.Char(required=True)
    iot_box_id = fields.Many2one('iot.box', compute='_compute_iot_box_id')

    def _get_default_pos(self):
        """Get the first PoS config where no IoT Box is set."""
        pos_config = self.env['pos.config'].search([('is_posbox', '=', False)], limit=1)
        return [(6, 0, [pos_config.id])] if pos_config else []

    @api.depends('iot_box_identifier')
    def _compute_iot_box_id(self):
        self.iot_box_id = self.env['iot.box'].search([('identifier', '=', self.iot_box_identifier)], limit=1)

    def action_autoconfigure(self):
        if not self.iot_box_id:
            return

        iot_box_devices = self.iot_box_id.device_ids

        device_types = {
            'display': 'iface_display_id',
            'printer': 'iface_printer_id',
            'scanner': 'iface_scanner_ids'
        }

        usb_receipt_printer = next(
            (device for device in iot_box_devices if device.type == 'printer' and device.subtype == 'receipt_printer' and device.connection == 'direct'),
            None
        )

        for pos_config in self.pos_config_ids:
            pos_config.is_posbox = True

            for device in iot_box_devices:
                if device.company_id.id not in [False, self.env.company.id]:
                    continue

                if device.type == 'printer':
                    if (usb_receipt_printer and device != usb_receipt_printer) or device.subtype != 'receipt_printer':
                        continue

                if device.type == 'scanner':
                    pos_config.iface_scanner_ids |= device
                elif device.type in device_types:
                    pos_config[device_types[device.type]] = device

        return {'type': 'ir.actions.act_window_close'}
