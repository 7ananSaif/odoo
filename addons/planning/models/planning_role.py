# Part of Odoo. See LICENSE file for full copyright and licensing details.
from random import randint

from odoo import fields, models


class PlanningRole(models.Model):
    _name = 'planning.role'
    _description = "Planning Role"
    _order = 'sequence'
    _rec_name = 'name'

    def _get_default_color(self):
        return randint(1, 11)

    active = fields.Boolean('Active', default=True)
    name = fields.Char('Name', required=True, translate=True)
    color = fields.Integer("Color", default=_get_default_color)
    resource_ids = fields.Many2many('resource.resource', 'resource_resource_planning_role_rel',
                                    'planning_role_id', 'resource_resource_id', 'Resources')
    sequence = fields.Integer(export_string_translation=False)
    slot_properties_definition = fields.PropertiesDefinition('Planning Slot Properties')

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [dict(vals, name=self.env._("%s (copy)", role.name)) for role, vals in zip(self, vals_list)]

    def _get_color_from_code(self, is_open_shift):
        """Take a color code from Odoo's Kanban view and returns an hex code compatible with the fullcalendar library"""
        # if the shift is an open shift, we use the '80' affix at the end of the hex code to modify the transparency
        if is_open_shift:
            switch_color = {
                0: '#00878480',   # No color (doesn't work actually...)
                1: '#EE4B3980',   # Red
                2: '#F2964880',   # Orange
                3: '#F4C60980',   # Yellow
                4: '#55B7EA80',   # Light blue
                5: '#71405B80',   # Dark purple
                6: '#E8686980',   # Salmon pink
                7: '#00878480',   # Medium blue
                8: '#26728380',   # Dark blue
                9: '#BF125580',   # Fushia
                10: '#2BAF7380',  # Green
                11: '#8754B080'   # Purple
            }
        else:
            switch_color = {
                0: '#008784',   # No color (doesn't work actually...)
                1: '#EE4B39',   # Red
                2: '#F29648',   # Orange
                3: '#F4C609',   # Yellow
                4: '#55B7EA',   # Light blue
                5: '#71405B',   # Dark purple
                6: '#E86869',   # Salmon pink
                7: '#008784',   # Medium blue
                8: '#267283',   # Dark blue
                9: '#BF1255',   # Fushia
                10: '#2BAF73',  # Green
                11: '#8754B0'   # Purple
            }
        return switch_color[self.color]

    def _get_light_color(self, factor, is_open_shift):
        factor = max(0.0, min(factor, 1.0))
        color = self._get_color_from_code(is_open_shift)
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        r = round(r + (255 - r) * factor)
        g = round(g + (255 - g) * factor)
        b = round(b + (255 - b) * factor)

        return f"#{r:02x}{g:02x}{b:02x}"
