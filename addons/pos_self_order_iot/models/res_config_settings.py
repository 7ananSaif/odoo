from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_self_ordering_iot_available_iot_box_ids = fields.One2many(
        related="pos_config_id.self_ordering_iot_available_iot_box_ids", domain="[('can_be_kiosk', '=', True)]", readonly=False
    )
