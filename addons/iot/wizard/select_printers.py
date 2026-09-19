# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SelectPrintersWizard(models.TransientModel):
    _name = 'select.printers.wizard'
    _description = "Selection of printers"

    device_ids = fields.Many2many('iot.device', domain=[('type', '=', 'printer')])
    display_device_ids = fields.Many2many('iot.device', relation='display_device_id_select_printer', domain=[('type', '=', 'printer')])
    do_not_ask_again = fields.Boolean("Do not ask me again", help="If checked, this dialog won't appear the next time you print and the selected printers will be used automatically.")
