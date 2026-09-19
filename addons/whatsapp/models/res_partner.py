# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, _
from odoo.addons.phone_validation.tools import phone_validation
from odoo.addons.whatsapp.tools import phone_validation as phone_validation_wa

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    wa_channel_count = fields.Integer(string='WhatsApp Channel Count', compute="_compute_wa_channel_count")

    def _compute_wa_channel_count(self):
        partner_channel_counts = {partner.id: 0 for partner in self}
        member_count_by_partner = self.env['discuss.channel.member']._read_group(
            domain=[
                ('channel_id.channel_type', '=', 'whatsapp'),
                ('partner_id', 'in', self.ids)
            ],
            groupby=['partner_id'],
            aggregates=['id:count'],
        )
        for partner, count in member_count_by_partner:
            partner_channel_counts[partner.id] += count
        for partner in self:
            partner.wa_channel_count = partner_channel_counts[partner.id]

    def _find_or_create_from_number(self, number, name=False):
        """ Number should come currently from whatsapp and contain country info. """
        search_number = number if number.startswith('+') else f'+{number}'
        try:
            formatted_number = phone_validation_wa.wa_phone_format(
                self.env.company,
                number=search_number,
                force_format='E164',
                raise_exception=True,
            )
        except Exception:  # noqa: BLE001 don't want to crash in that point, whatever the issue
            _logger.warning('WhatsApp: impossible to format incoming number %s, skipping partner creation', number)
            formatted_number = False
        if not number or not formatted_number:
            return self.env['res.partner']

        # find country / local number based on formatted number to ease future searches
        region_data = phone_validation.phone_get_region_data_for_number(formatted_number)
        number_country_code = region_data['code']
        number_national_number = str(region_data['national_number'])
        number_phone_code = int(region_data['phone_code'])

        # search partner on INTL number, then fallback on national number
        partners = self.search([('phone_mobile_search', '=', formatted_number)])
        if not partners:
            partners = self.search([('phone_mobile_search', '=like', number_national_number)])

        if not partners:
            # do not set a country if country code is not unique as we cannot guess
            country = self.env['res.country'].search([('phone_code', '=', number_phone_code)])
            if len(country) > 1:
                country = country.filtered(lambda c: c.code.lower() == number_country_code.lower())

            partners = self.env['res.partner'].create({
                'country_id': country.id if country and len(country) == 1 else False,
                'phone': formatted_number,
                'name': name or formatted_number,
            })
            partners._message_log(
                body=_("Partner created by incoming WhatsApp message.")
            )
        return partners[0]

    def action_open_partner_wa_channels(self):
        return {
            'name': _('WhatsApp Chats'),
            'type': 'ir.actions.act_window',
            'domain': [('channel_type', '=', 'whatsapp'), ('channel_partner_ids', 'in', self.ids)],
            'res_model': 'discuss.channel',
            'views': [(self.env.ref('whatsapp.discuss_channel_view_list_whatsapp').id, 'list')],
        }
