# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models


class DiscoveredIotBox(models.TransientModel):
    _name = 'iot.discovered.box'
    _description = 'An IoT box that is in pairing mode'

    name = fields.Char(compute="_compute_box_name")
    add_iot_box_wizard_id = fields.Many2one("add.iot.box")
    serial_number = fields.Char(readonly=True)
    pairing_code = fields.Char(readonly=True)

    def _compute_box_name(self):
        for box in self:
            box.name = _("IoT Box %(serial_n)s %(pairing_code)s", serial_n=box.serial_number or "", pairing_code=box.pairing_code)
