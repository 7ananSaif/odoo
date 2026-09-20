# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import Counter

from odoo import api, fields, models
from markupsafe import Markup


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    coupons_count = fields.Integer(compute='_compute_coupons_count', export_string_translation=False)
    gift_card_count = fields.Integer(compute='_compute_coupons_count', export_string_translation=False)
    coupon_ids = fields.Many2many('loyalty.card', string='Generated Coupons', copy=False)
    default_giftcard_program_id = fields.Many2one(
        'loyalty.program',
        default=lambda self: self.env['loyalty.program'].search([('program_type', '=', 'gift_card')], limit=1),
        domain=[('program_type', '=', 'gift_card')],
        export_string_translation=False,
    )

    @api.depends('coupon_ids')
    def _compute_coupons_count(self):
        for ticket in self:
            type_counts = Counter(ticket.coupon_ids.mapped('program_type'))
            ticket.coupons_count = type_counts.get('coupons', 0)
            ticket.gift_card_count = type_counts.get('gift_card', 0)

    def open_coupons(self):
        self.ensure_one()
        program = self.env.context.get('program_type')
        coupon_ids = self.coupon_ids.filtered(lambda coupon: coupon.program_type == program)
        count = self.coupons_count if program == 'coupons' else self.gift_card_count
        if program == 'coupon':
            no_content_message = self.env._('No gift cards found')
            help_message = self.env._('Reimburse customers with a voucher code for future purchases')
        else:
            no_content_message = self.env._('No Coupon found')
            help_message = self.env._('Create a new one from scratch')
        help = Markup("""
                <p class='o_view_nocontent_smiling_face'>{}</p>
                <p>{}</p>
        """).format(no_content_message, help_message)

        action = {
            'type': 'ir.actions.act_window',
            'name': self.env._('Coupons') if program == 'coupons' else self.env._('Gift Cards'),
            'res_model': 'loyalty.card',
            'view_mode': 'list,form',
            'domain': [('id', 'in', coupon_ids.ids)],
            'context': dict(
                self.env.context, create=False, edit=False, default_company_id=self.company_id.id, program_type=False
            ),
            'help': help,
        }
        if count == 1:
            action.update({
                'view_mode': 'form',
                'res_id': coupon_ids.id
            })
        return action
