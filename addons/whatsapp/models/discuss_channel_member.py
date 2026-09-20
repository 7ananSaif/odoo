# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import api, models
from odoo.fields import Domain
from odoo.addons.mail.tools.discuss import Store


class DiscussChannelMember(models.Model):
    _inherit = 'discuss.channel.member'

    @api.autovacuum
    def _gc_unpin_whatsapp_channels(self):
        """ Unpin read whatsapp channels with no activity for at least one day to
            clean the operator's interface. """
        one_day_ago = datetime.now() - timedelta(days=1)
        five_days_ago = datetime.now() - timedelta(days=5)
        members = self.env['discuss.channel.member'].search(Domain.AND([
            [("is_pinned", "=", True)],
            [("channel_id.channel_type", "=", "whatsapp")],
            Domain.OR([
                [("last_seen_dt", "<", one_day_ago)],
                [
                    ("last_seen_dt", "=", False),
                    ("channel_id.create_date", "<=", five_days_ago),
                ],
            ]),
        ]), limit=1000)
        members_to_be_unpinned = members.filtered(
            lambda m: m.message_unread_counter == 0 or (not m.last_seen_dt and m.channel_id.create_date <= five_days_ago) or m.last_seen_dt <= five_days_ago
        )
        members_to_be_unpinned.unpin_dt = datetime.now()
        for member in members_to_be_unpinned:
            Store(bus_channel=member._bus_channel()).add(
                member.channel_id, {"close_chat_window": True}
            ).bus_send()
