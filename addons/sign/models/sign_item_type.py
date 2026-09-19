# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SignItemType(models.Model):
    _name = 'sign.item.type'
    _description = "Signature Item Type"

    active = fields.Boolean("Active", default=True)
    name = fields.Char(string="Field Name", required=True, translate=True)
    icon = fields.Char()
    item_type = fields.Selection([
        ('signature', "Signature"),
        ('initial', "Initial"),
        ('text', "Text"),
        ('textarea', "Multiline Text"),
        ('checkbox', "Checkbox"),
        ('radio', "Radio"),
        ('selection', "Selection"),
        ('strikethrough', "Strikethrough"),
        ('stamp', "Stamp"),
    ], required=True, string='Type', default='text')

    tip = fields.Char(required=True, default="Fill in", help="Hint displayed in the signing hint", translate=True)
    placeholder = fields.Char(translate=True)

    field_size = fields.Selection([
            ('short_text', "Short Text"),
            ('regular_text', "Regular Text"),
            ('long_text', "Long Text"),
        ], string="Field Size", default='regular_text', required=True,
    )
    default_width = fields.Float(string="Default Width", digits=(4, 3), required=True, default=0.150, compute="_compute_dimensions")
    default_height = fields.Float(string="Default Height", digits=(4, 3), required=True, default=0.015, compute="_compute_dimensions")
    model_id = fields.Many2one('ir.model', string="Linked to",
                                domain=[('model', '!=', 'sign.request'), ('is_mail_thread', '=', 'True')])
    model_name = fields.Char(related='model_id.model')
    auto_field = fields.Char(string="Linked field", groups='base.group_system',
                             help="Technical name of the field on the partner model to auto-complete this signature field at the time of signature.")

    @api.constrains('auto_field')
    def _check_auto_field_exists(self):
        for sign_type in self:
            if sign_type.auto_field and sign_type.model_id.model:
                record = self.env[sign_type.model_id.model]
                try:
                    auto_field_value = record.mapped(sign_type.auto_field)
                except KeyError:
                    auto_field_value = None
                if auto_field_value is None or isinstance(auto_field_value, models.BaseModel):
                    raise ValidationError(_("Malformed expression: %(exp)s", exp=sign_type.auto_field))

    @api.depends('field_size', 'item_type')
    def _compute_dimensions(self):
        text_dimension_map = {
            'short_text': {'width': 0.1, 'height': 0.015},
            'regular_text': {'width': 0.18, 'height': 0.015},
            'long_text': {'width': 0.3, 'height': 0.015},
        }

        default_dimension_map = {
            'signature': [0.2, 0.05],
            'initial': [0.085, 0.03],
            'text': [0.18, 0.015],
            'textarea': [0.2, 0.05],
            'checkbox': [0.02, 0.018],
            'radio': [0.02, 0.018],
            'selection': [0.18, 0.015],
            'strikethrough': [0.18, 0.015],
            'stamp': [0.298, 0.092],
        }

        for record in self:
            if record.item_type == 'text':
                dimensions = text_dimension_map.get(record.field_size, {})
                record.default_width = dimensions.get('width', record.default_width)
                record.default_height = dimensions.get('height', record.default_height)
            else:
                record.default_width = default_dimension_map[record.item_type][0]
                record.default_height = default_dimension_map[record.item_type][1]
