import re
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.tools import is_html_empty, plaintext2html
from odoo.addons.mail.tools.discuss import Store


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    ticket_ids = fields.One2many(
        "helpdesk.ticket",
        "origin_channel_id",
        string="Tickets",
        groups="helpdesk.group_helpdesk_user",
        help="The channel becomes accessible to helpdesk users when tickets are set.",
    )
    has_helpdesk_ticket = fields.Boolean(compute="_compute_has_helpdesk_ticket", store=True)
    _has_helpdesk_ticket_index = models.Index("(has_helpdesk_ticket) WHERE has_helpdesk_ticket IS TRUE")

    @api.depends("ticket_ids")
    def _compute_has_helpdesk_ticket(self):
        for channel in self:
            channel.has_helpdesk_ticket = bool(channel.ticket_ids)

    # ------------------------------------------------------
    #  Commands
    # ------------------------------------------------------

    def execute_command_helpdesk(self, **kwargs):
        key = kwargs.get('body').split()
        msg = _('Something is missing or wrong in the command')
        partners = self.with_context(active_test=False).channel_partner_ids.filtered(lambda partner: partner != self.env.user.partner_id)
        ticket_command = "/ticket"
        if key[0].lower() == ticket_command:
            if len(key) == 1:
                msg = _(
                    "Create a new helpdesk ticket with: "
                    "%(pre_start)s%(ticket_command)s %(i_start)sticket title%(i_end)s%(pre_end)s",
                    ticket_command=ticket_command,
                    pre_start=Markup("<pre>"),
                    pre_end=Markup("</pre>"),
                    i_start=Markup("<i>"),
                    i_end=Markup("</i>"),
                )
            else:
                customer = partners[:1]
                list_value = key[1:]
                description = ''
                odoobot = self.env.ref('base.partner_root')
                for message in self.message_ids.sorted(key=lambda r: r.id):
                    if (not message.attachment_ids and is_html_empty(message.body)) or message.author_id == odoobot:
                        continue
                    name = message.author_id.name or 'Anonymous'
                    if message.body:
                        description += '%s: ' % name + '%s\n' % re.sub('<[^>]*>', '', message.body)
                    attachment_author_shown = False
                    for attachment in message.attachment_ids:
                        if not message.body and not attachment_author_shown:
                            description += '%s:\n' % name
                            attachment_author_shown = True
                        description += Markup("%s<br/>") % self._attachment_to_html(attachment)
                team = self.env['helpdesk.team'].search([('use_website_helpdesk_livechat', '=', True)], order='sequence', limit=1)
                team_id = team.id if team else False
                helpdesk_ticket = self.env['helpdesk.ticket'].with_context(with_partner=True).create({
                    "origin_channel_id": self.id,
                    'name': ' '.join(list_value),
                    'description': plaintext2html(description),
                    'partner_id': customer.id if customer else False,
                    'team_id': team_id,
                })
                # We copy the non-image attachments and update their id/model to attach them to the ticket.
                self.message_ids.attachment_ids.filtered(
                    lambda attachment: 'image/' not in attachment.mimetype
                ).copy({
                    'res_id': helpdesk_ticket.id,
                    'res_model': 'helpdesk.ticket',
                })
                msg = _("Created a new ticket: %s", helpdesk_ticket._get_html_link())
        self.env.user._bus_send_transient_message(self, msg)

    def fetch_ticket_by_keyword(self, list_keywords, load_counter=0):
        keywords = re.findall(r'\w+', ' '.join(list_keywords))
        helpdesk_tag_ids = self.env['helpdesk.tag'].search(
            Domain.OR(Domain('name', 'ilike', keyword) for keyword in keywords)
        ).ids
        tickets = self.env['helpdesk.ticket'].search([('tag_ids', 'in', helpdesk_tag_ids)], offset=load_counter*5, limit=6, order='id desc')
        if not tickets:
            for Keyword in keywords:
                tickets |= self.env['helpdesk.ticket'].search([
                    '|', '|', '|', '|', '|',
                    ('name', 'ilike', Keyword),
                    ('ticket_ref', 'ilike', Keyword),
                    ('partner_id.id', 'ilike', Keyword),
                    ('partner_name', 'ilike', Keyword),
                    ('partner_email', 'ilike', Keyword),
                    ('partner_phone', 'ilike', Keyword),
                ], order="id desc", offset=load_counter*5, limit=6 - len(tickets))
        if not tickets:
            return False
        load_more = False
        if len(tickets) > 5:
            tickets = tickets[:-1]
            load_more = True
        msg = Markup('<br/>').join(ticket.with_context(with_partner=True)._get_html_link() for ticket in tickets)
        if load_more:
            msg += Markup('<br/>')
            msg += Markup('<div class="o_load_more"><b><a href="#" data-oe-type="load" data-oe-lst="%s" data-oe-load-counter="%s">%s</a></b></div>') % (
                ' '.join(list_keywords),
                load_counter + 1,
                _('Load More')
            )
        return msg

    def execute_command_helpdesk_search(self, **kwargs):
        key = kwargs.get('body').split()
        partner = self.env.user.partner_id
        msg = _('Something is missing or wrong in command')
        search_tickets_command = "/search_tickets"
        if key[0].lower() == search_tickets_command:
            if len(key) == 1:
                msg = _(
                    "Search helpdesk tickets by typing: "
                    "%(pre_start)s%(search_tickets_command)s %(i_start)skeywords%(i_end)s%(pre_end)s",
                    search_tickets_command=search_tickets_command,
                    pre_start=Markup("<pre>"),
                    pre_end=Markup("</pre>"),
                    i_start=Markup("<i>"),
                    i_end=Markup("</i>"),
                )
            else:
                list_keywords = key[1:]
                tickets = self.fetch_ticket_by_keyword(list_keywords)
                if tickets:
                    msg = _(
                        "Tickets search results for %(b_start)s%(keywords)s%(b_end)s: %(br)s%(tickets)s",
                        keywords=" ".join(list_keywords),
                        b_start=Markup("<b>"),
                        b_end=Markup("</b>"),
                        br=Markup("<br/>"),
                        tickets=tickets,
                    )
                else:
                    msg = _(
                        "No tickets found for %(b_start)s%(keywords)s%(b_end)s.%(br)s"
                        "Make sure you are using the right format: "
                        "%(pre_start)s%(search_tickets_command)s %(i_start)skeywords%(i_end)s%(pre_end)s",
                        keywords=" ".join(list_keywords),
                        b_start=Markup("<b>"),
                        b_end=Markup("</b>"),
                        br=Markup("<br/>"),
                        search_tickets_command=search_tickets_command,
                        pre_start=Markup("<pre>"),
                        pre_end=Markup("</pre>"),
                        i_start=Markup("<i>"),
                        i_end=Markup("</i>"),
                    )
        partner._bus_send_transient_message(self, msg)

    def _get_livechat_session_fields_to_store(self):
        fields_to_store = super()._get_livechat_session_fields_to_store()
        if not self.env["helpdesk.ticket"].has_access("read"):
            return fields_to_store
        # Fetch all parent partners and children recursively to get partners from the same company
        partners = self.livechat_customer_partner_ids
        while True:
            new_partners = partners | partners.parent_id
            if partners == new_partners:
                break
            partners = new_partners
        while True:
            new_partners = partners | partners.child_ids
            if partners == new_partners:
                break
            partners = new_partners
        helpdesk_tickets = self.env["helpdesk.ticket"].search(
            Domain("partner_id", "in", partners.ids)
            & (
                Domain("team_id.message_follower_ids.partner_id", "=", self.env.user.partner_id.id)
                | Domain("message_follower_ids.partner_id", "=", self.env.user.partner_id.id)
            ),
            limit=5,
        )
        fields_to_store.append(
            Store.Many(
                "livechat_customer_partner_ids",
                [
                    Store.Many(
                        "helpdesk_tickets",
                        ["id", "name"],
                        value=helpdesk_tickets,
                    )
                ],
            ),
        )
        return fields_to_store
