# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SignItem(models.Model):
    _name = 'sign.item'
    _description = "Fields to be sign on Document"
    _order = "page asc, posY asc, posX asc"
    _rec_name = 'document_id'

    document_id = fields.Many2one('sign.document', string="Document Template", required=True, index=True, ondelete='cascade')
    template_id = fields.Many2one('sign.template', related='document_id.template_id')
    type_id = fields.Many2one('sign.item.type', string="Type", required=True, ondelete='restrict')

    required = fields.Boolean(default=True)
    responsible_id = fields.Many2one("sign.item.role", string="Responsible", ondelete="restrict")

    option_ids = fields.Many2many("sign.item.option", string="Selection options", relation='sign_item_option_rel')

    radio_set_id = fields.Many2one("sign.item.radio.set", string="Radio button options", ondelete='cascade', index='btree_not_null')
    num_options = fields.Integer(related="radio_set_id.num_options")

    name = fields.Char(string="Field Name", default=lambda self: self.type_id.placeholder)
    page = fields.Integer(string="Document Page", required=True, default=1)
    posX = fields.Float(digits=(4, 3), string="Position X", required=True)
    posY = fields.Float(digits=(4, 3), string="Position Y", required=True)
    width = fields.Float(digits=(4, 3), required=True)
    height = fields.Float(digits=(4, 3), required=True)
    alignment = fields.Char(default="left", required=True)
    constant = fields.Boolean(string="Read-only")

    transaction_id = fields.Integer(copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.template_id.check_access('write')
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.keys() & {'template_id', 'document_id'}:
            self.template_id.check_access('write')
        return res

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        # When duplicating sign items of type "radio" create new equivalent radio sets for the new items.
        radio_set_map = {}
        for radio_set_id in {item['radio_set_id'] for item in vals_list if item['radio_set_id']}:
            new_radio_set = self.env['sign.item.radio.set'].create([{}])
            radio_set_map[radio_set_id] = new_radio_set.id
        for item in vals_list:
            item['radio_set_id'] = radio_set_map.get(item['radio_set_id'])
        return vals_list

    @api.constrains('required', 'constant')
    def _check_constant(self):
        for record in self:
            if record.constant and record.type_id.item_type in ['signature', 'initial', 'selection', 'checkbox', 'radio']:
                raise ValidationError(self.env._("Read-only can only be applied to items of the following types: 'Text', 'Name', 'Email', 'Phone', 'Company', 'Multiline', 'Date', 'Strikethrough'"))

    @api.autovacuum
    def _gc_radio_set_and_options(self):
        # Unlink orphaned radio sets that has no sign items linked to it
        self.env.cr.execute("""
            WITH linked_radio AS (
                SELECT s.id radio_id
                FROM sign_item_radio_set s
                LEFT JOIN sign_item si ON si.radio_set_id=s.id
                WHERE si.id IS NULL
            )
            DELETE FROM sign_item_radio_set
            WHERE id IN (SELECT * FROM linked_radio)
        """)
        # Unlink options that don't belong to any selection sign item
        self.env.cr.execute("""
            DELETE FROM sign_item_option
            WHERE id NOT IN (SELECT sign_item_option_id FROM sign_item_option_rel)
        """)
