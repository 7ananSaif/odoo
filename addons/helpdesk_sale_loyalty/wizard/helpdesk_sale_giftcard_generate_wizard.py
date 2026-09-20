# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup
from odoo.exceptions import ValidationError

from odoo import fields, models


class HelpdeskSaleGiftcardGenerateWizard(models.TransientModel):
    _inherit = 'loyalty.generate.wizard'
    _description = 'Generate Gift Card Wizard'

    ticket_id = fields.Many2one('helpdesk.ticket', export_string_translation=False)
    company_id = fields.Many2one(related='ticket_id.company_id', export_string_translation=False)

    def generate_giftcard(self):
        if not self.program_id:
            raise ValidationError(self.env._('Unable to generate Gift Card(s), please set a program first.'))

        self.coupon_qty = 1
        self.mode = 'selected'
        self.customer_ids = self.ticket_id.partner_id
        coupon = self.generate_coupons()
        coupon.ensure_one()
        self.ticket_id.coupon_ids |= coupon

        for message in coupon.website_message_ids:
            self.ticket_id.message_post(body=message.body, attachment_ids=message.attachment_ids.ids)

        action_id = self.env.ref('helpdesk_sale_loyalty.loyalty_open_card_action').id
        url = f'/odoo/helpdesk/{self.ticket_id.team_id.id}/tickets/{self.ticket_id.id}/action-{action_id}/{coupon.id}'
        url = Markup("<a href='%s'>%s</a>") % (url, coupon.display_name)
        self.ticket_id.message_post(body=self.env._('%s Gift Card created', url))

        coupon.message_post_with_source(
            'mail.message_origin_link',
            render_values={'self': coupon, 'origin': self.ticket_id},
            subtype_xmlid='mail.mt_note',
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': 'Gift card generated and sent',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
