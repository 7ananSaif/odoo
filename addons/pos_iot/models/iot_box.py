# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class IotBox(models.Model):
    _name = 'iot.box'
    _inherit = ['iot.box', 'pos.load.mixin']

    associated_pos_config_ids = fields.Many2many(
        'pos.config', string="Associated PoS", compute='_compute_associated_pos_config_ids'
    )

    @api.model
    def _load_pos_data_domain(self, data, config):
        return [('id', 'in', [device['iot_id'] for device in data['iot.device'] if device['iot_id']])]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['ip', 'name', 'identifier']

    @api.depends('device_ids')
    def _compute_associated_pos_config_ids(self):
        """Compute the associated PoS config ids for the IoT Box."""
        for box in self:
            domain = Domain('is_posbox', '=', True) & Domain.OR(
                Domain(field_name, 'in', box.device_ids.ids)
                for field_name in (
                    'iface_printer_id', 'iface_display_id', 'iface_scale_id', 'iface_scanner_ids'
                )
            )
            box.associated_pos_config_ids = self.env['pos.config'].search(domain)
