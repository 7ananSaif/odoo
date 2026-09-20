# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def set_param(self, key, value):
        if key == 'web.base.url' and not value.startswith('http://localhost'):
            iot_box_identifiers = self.env['iot.box'].search([]).mapped('identifier')
            self.env['iot.channel'].send_message({
                'iot_identifiers': iot_box_identifiers,
                'server_url': value,
            }, 'server_update')

        return super().set_param(key, value)
