from odoo import models


class AutoConfigPoSIoT(models.TransientModel):
    _inherit = 'auto.config.pos.iot'

    def action_autoconfigure(self):
        if not self.iot_box_id:
            return

        for pos_config in self.pos_config_ids:
            if pos_config.self_ordering_mode == 'kiosk' and self.iot_box_id.can_be_kiosk:
                pos_config.self_ordering_iot_available_iot_box_ids = [(4, self.iot_box_id.id)]

        return super().action_autoconfigure()
