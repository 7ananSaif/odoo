# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from markupsafe import Markup
import pytz

from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.tools.urls import urljoin as url_join


class FrontdeskVisitor(models.Model):
    _name = 'frontdesk.visitor'
    _description = 'Frontdesk Visitors'
    _inherit = ['mail.thread']
    _order = 'check_in'

    active = fields.Boolean(default=True)
    name = fields.Char('Name', required=True)
    phone = fields.Char('Phone')
    email = fields.Char('Email')
    company = fields.Char('Visitor Company')
    message = fields.Html()
    host_ids = fields.Many2many(
        'hr.employee', string='Host Name',
        domain="[('company_id', '=', company_id), '|', ('work_email', '!=', False), ('work_phone', '!=', False)]"
    )
    drink_ids = fields.Many2many('frontdesk.drink', string='Drinks')
    check_in = fields.Datetime(string='Check In')
    check_out = fields.Datetime(string='Check Out')
    duration = fields.Float('Duration', compute="_compute_duration", store=True, default=1.0)
    state = fields.Selection(string='Status',
        selection=[('planned', 'Planned'),
                   ('checked_in', 'Checked-In'),
                   ('checked_out', 'Checked-Out'),
                   ('canceled', 'Cancelled')],
        default='planned', tracking=True
    )
    station_id = fields.Many2one('frontdesk.frontdesk', required=True, index=True)
    visitor_properties = fields.Properties('Properties', definition='station_id.visitor_properties_definition', copy=True)
    served = fields.Boolean(string='Drink Served')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._check_and_notify_visitor()
        return res

    def write(self, vals):
        if vals.get('state') == 'checked_in':
            vals['check_in'] = fields.Datetime.now()
            self._notify()
            if self.drink_ids:
                self._notify_to_people()
        elif vals.get('state') == 'checked_out':
            vals['check_out'] = fields.Datetime.now()
            vals['served'] = True
        return super().write(vals)

    @api.depends('check_in', 'check_out')
    def _compute_duration(self):
        for visitor in self:
            if visitor.check_in and visitor.check_out:
                visitor.duration = (visitor.check_out - visitor.check_in).total_seconds() / 3600

    def action_check_in(self):
        self.ensure_one()
        self.state = 'checked_in'

    def action_canceled(self):
        self.ensure_one()
        self.state = 'canceled'

    def action_planned(self):
        self.ensure_one()
        self.state = 'planned'

    def action_check_out(self):
        self.ensure_one()
        self.state = 'checked_out'

    def action_served(self):
        self.ensure_one()
        self.served = True

    def _notify(self):
        """ Send a notification to the frontdesk's responsible users and the visitor's hosts when the visitor checks in. """
        for visitor in self:
            msg = ""
            visitor_name = visitor.name
            visitor_name += f" ({visitor.phone})" if visitor.phone else ""
            visitor_name += f" ({visitor.company})" if visitor.company else ""
            if visitor.station_id.responsible_ids:
                if visitor.host_ids:
                    host_info = ', '.join([f'{host.name}' for host in visitor.host_ids])
                    msg = _("%(station)s Check-In: %(visitor)s to meet %(host)s", station=visitor.station_id.name, visitor=visitor_name, host=host_info)
                else:
                    msg = _("%(station)s Check-In: %(visitor)s", station=visitor.station_id.name, visitor=visitor_name)
                visitor._notify_by_discuss(visitor.station_id.responsible_ids, msg)
            if visitor.station_id.host_selection and visitor.host_ids:
                if visitor.station_id.notify_discuss:
                    msg = _("%s just checked-in.", visitor_name)
                    for host in visitor.host_ids:
                        if host.user_id:
                            visitor._notify_by_discuss([host], msg, True)
                        elif not visitor.station_id.notify_email and host.work_email:
                            visitor._notify_by_email()
                        elif not visitor.station_id.notify_sms and host.work_phone:
                            visitor._notify_by_sms()
                if visitor.station_id.notify_email:
                    visitor._notify_by_email()
                if visitor.station_id.notify_sms:
                    visitor._notify_by_sms()

    def _notify_to_people(self):
        """ Send notification to the drink's responsible users when the visitor checks in. """
        for visitor in self:
            if visitor.drink_ids.notify_user_ids:
                action = visitor.env.ref('frontdesk.action_frontdesk_visitor').id
                name = f"{self.name} ({self.company})" if self.company else self.name
                msg = _("%(name)s just checked-in. Requested Drink: %(drink)s.",
                    name=Markup('<a href="%s">%s</a>') % (
                        url_join(self.env['frontdesk.visitor'].get_base_url(), f'/odoo/action-{action}/{visitor.id}'), name
                    ),
                    drink=', '.join(drink.name for drink in visitor.drink_ids),
                )
                visitor._notify_by_discuss(visitor.drink_ids.notify_user_ids, msg)

    def _notify_by_discuss(self, recipients, msg, is_host=False):
        for recipient in recipients:
            if is_host and (not recipient.user_id or not recipient.user_id.partner_id):
                continue
            odoobot_id = self.env.ref("base.partner_root").id
            partners_to = [recipient.user_partner_id.id] if is_host else [recipient.partner_id.id]
            channel = self.env["discuss.channel"].with_user(SUPERUSER_ID)._get_or_create_chat(partners_to)
            channel.message_post(body=msg, author_id=odoobot_id, message_type="comment", subtype_xmlid="mail.mt_comment")

    def _notify_by_email(self):
        for host in self.host_ids:
            if host.work_email:
                odoobot = self.env.ref('base.partner_root')
                values = {'host_name': host.name, 'object': self}
                body = self.env['ir.qweb']._render('frontdesk.frontdesk_mail_template', values, lang=host.user_partner_id.lang)
                self.message_post(
                    email_from=odoobot.email_formatted,
                    author_id=self.env.user.partner_id.id,
                    body=body,
                    subject=_('Your Visitor %(name)s Requested To Meet You', name=self.name),
                    partner_ids=host.work_contact_id.ids,
                    message_type='email',
                    subtype_xmlid='mail.mt_comment',
                    email_layout_xmlid='mail.mail_notification_light',
                    force_send=True,
                )

    def _notify_by_sms(self):
        self.ensure_one()
        self._message_sms_with_template(
                template=self.station_id.sms_template_id,
                partner_ids=self.host_ids.filtered('work_phone').work_contact_id.ids,
        )

    def _get_host_name(self):
        return ", ".join(self.host_ids.mapped('name'))

    def _check_resources_leave(self, resources, check_in):
        if not resources or not check_in:
            return []
        start = pytz.utc.localize(check_in)
        stop = start + timedelta(minutes=1)
        calendar = self.env.company.resource_calendar_id
        leaves = calendar._leave_intervals_batch(start, stop, resources=resources)
        resource_on_leave = [resource.id for resource in resources if leaves[resource.id]._items]
        return resource_on_leave

    def _check_and_notify_visitor(self):
        resources = [host.resource_id for host in self.host_ids]
        odoobot = self.env.ref('base.partner_root')
        author = self.station_id.company_id.partner_id
        for visitor in self:
            resources_on_leave = self._check_resources_leave(resources, visitor.check_in)
            hosts_on_leave = visitor.host_ids.filtered(lambda host: host.resource_id.id in resources_on_leave)
            if hosts_on_leave:
                body = Markup(
                    """<div>
                        <p>%(greeting)s</p>
                        <p>%(message)s</p>
                        <ul>
                            %(host_details)s
                        </ul>
                        <p>%(footer_contact)s</p>
                        <p>%(footer)s</p>
                    </div>"""
                ) % {
                    "greeting": _("Dear %(visitor_name)s,", visitor_name=visitor.name),
                    "message": _(
                        "We regret to inform you that the following %(host_status)s currently unavailable:",
                        host_status=_('host is') if len(hosts_on_leave) == 1 else _('hosts are')
                    ),
                    "host_details": Markup().join(
                        Markup("<li><strong>%(host_name)s</strong>%(manager_info)s</li>") % {
                            "host_name": host.name,
                            "manager_info": _(' - Manager: %(manager_name)s', manager_name=host.parent_id.name)
                            if host.parent_id else ''
                        }
                        for host in hosts_on_leave
                    ),
                    "footer_contact": _(
                        "You can contact the host's manager or frontdesk responsible for further assistance."
                    ),
                    "footer": _("Thanks for your understanding.")
                }
                if visitor.email and visitor.station_id.ask_email in ['required', 'optional']:
                    visitor.message_post(
                        body=body,
                        subject=_("Your host isn't available"),
                        author_id=author.id,
                        message_type="comment",
                        subtype_xmlid="mail.mt_comment"
                    )
                if visitor.phone and visitor.station_id.ask_phone in ['required', 'optional']:
                    visitor._message_sms(
                        author_id=odoobot.id,
                        body=body,
                        sms_numbers=[visitor.phone],
                    )
