import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    self_ordering_iot_available_iot_box_ids = fields.One2many(
        'iot.box',
        'pos_id',
        string='Available IoT Boxes',
        domain="[('can_be_kiosk', '=', True)]",
        required=True,
    )

    def _get_kitchen_printer(self):
        res = super()._get_kitchen_printer()
        for printer in self.printer_ids:
            if printer.device_identifier:
                res[printer.id]["device_identifier"] = printer.device_identifier
        return res

    def _load_self_data_models(self):
        models = super()._load_self_data_models()
        models += ['iot.device', 'iot.box']
        return models

    def action_open_wizard(self):
        """Override the ir.action.act_url to open the kiosk on the selected IoT Boxes (if any)."""
        url_in_new_tab_action = super().action_open_wizard()  # Configure pos session

        # If no IoT Box is selected in the settings, open the kiosk in a new tab
        if not self.self_ordering_iot_available_iot_box_ids:
            return url_in_new_tab_action

        display_identifiers = [
            d.identifier
            for box in self.self_ordering_iot_available_iot_box_ids
            for d in box.device_ids if d.type == 'display'
        ]

        self.env['iot.channel'].send_message({
            "iot_identifiers": [iot_box.identifier for iot_box in self.self_ordering_iot_available_iot_box_ids],
            "device_identifiers": display_identifiers,
            'action': 'open_kiosk',
            'pos_id': self.id,
            'access_token': self.access_token,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'message': _("Opening the kiosk on %s", ', '.join(self.self_ordering_iot_available_iot_box_ids.mapped('name'))),
            }
        }

    def has_valid_self_payment_method(self):
        res = super().has_valid_self_payment_method()
        if self.self_ordering_mode == 'mobile':
            return res
        return res or any(pm.iot_device_id for pm in self.payment_method_ids)
