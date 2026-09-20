# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SignItemRadioSet(models.Model):
    _name = 'sign.item.radio.set'
    _description = "Radio button set for keeping radio button items together"

    radio_items = fields.One2many('sign.item', 'radio_set_id')
    num_options = fields.Integer(string="Number of Radio Button options", compute="_compute_num_options")

    @api.depends('radio_items')
    def _compute_num_options(self):
        for radio_set in self:
            radio_set.num_options = len(radio_set.radio_items)
