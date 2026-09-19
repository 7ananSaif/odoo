# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import calendar as cal
import random
import pytz
from datetime import datetime, timedelta, time
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from babel.dates import format_datetime, format_time
from werkzeug.urls import url_encode

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.fields import Command, Domain
from odoo.tools import float_compare, frozendict
from odoo.tools.misc import babel_locale_parse, get_lang
from odoo.tools.urls import urljoin as url_join
from odoo.addons.base.models.res_partner import _tz_get


class AppointmentType(models.Model):
    _name = 'appointment.type'
    _description = "Appointment Type"
    _inherit = ['image.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = "sequence, id"
    _mail_post_access = 'read'

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)
        if 'category' not in fields or result.get('category') == 'custom':
            if 'name' in fields and not result.get('name'):
                result['name'] = _("%s - Let's meet", self.env.user.name)
            if 'staff_user_ids' in fields and not result.get('staff_user_ids'):
                result['staff_user_ids'] = [Command.set(self.env.user.ids)]
        if 'event_videocall_source' in fields and not result.get('event_videocall_source'):
            if not result.get('location_id'):
                result['event_videocall_source'] = self._get_default_event_videocall_source()
        return result

    def _default_booked_mail_template_id(self):
        return self.env['ir.model.data']._xmlid_to_res_id('appointment.attendee_invitation_mail_template')

    def _default_canceled_mail_template_id(self):
        return self.env['ir.model.data']._xmlid_to_res_id('appointment.appointment_canceled_mail_template')

    @api.model
    def _default_question_ids(self):
        return self.env['appointment.question'].search([('is_default', '=', True), ('active', '=', True)]).ids

    def _get_default_event_videocall_source(self):
        return 'discuss'

    # Global Settings
    sequence = fields.Integer('Sequence', default=10)
    name = fields.Char('Appointment Title', required=True, translate=True)
    active = fields.Boolean(default=True)

    # Global Appointment Type Settings
    appointment_duration = fields.Float('Duration', required=True, default=1.0)
    appointment_duration_formatted = fields.Char(
        'Appointment Duration Formatted ', compute='_compute_appointment_duration_formatted', readonly=True,
        help='Appointment Duration formatted in words')
    appointment_tz = fields.Selection(
        _tz_get, string='Timezone', required=True, default=lambda self: self.env.user.tz or 'UTC',
        help="Timezone where appointment take place")
    auto_confirm = fields.Boolean("Auto Confirm", default=True,
        help="""Automatically confirm appointments at creation, up to the given percentage of the total capacity reserved.
            If unchecked, the appointments will be created as requests and will need manual confirmation.
            Requested appointments are still considered as reserved for the slots availability""")
    # Technical field. True when bookings will always be confirmed
    # e.g. 1.0 manual_confirmation_percentage and auto_confirm True
    is_always_confirm = fields.Boolean(compute="_compute_is_always_confirm")
    image_1920 = fields.Image("Background Image")  # image.mixin override
    location_id = fields.Many2one('res.partner', string='Location')
    location = fields.Char(
        'Location formatted', compute='_compute_location', compute_sudo=True,
        help='Location formatted for one line uses')
    event_videocall_source = fields.Selection([('discuss', 'Odoo Discuss')], string="Video Link",
        help="Defines the type of video call link that will be used for the generated events. Keep it empty to prevent generating meeting url.")
    allow_guests = fields.Boolean(string='Allow invitations', help="Let attendees invite guests when registering a meeting.")
    manual_confirmation_percentage = fields.Float("Capacity Percentage", default=1.0,
        help="""Bookings will not be automatically confirmed once the total
        reserved user/resource capacity exceeds this percentage of total capacity.""")
    manage_capacity = fields.Boolean("Manage Capacities",
        help="""Manage the maximum amount of people a user/resource can handle (e.g. Table for 6 persons, ...)""")
    max_bookings = fields.Integer("Total Bookings", compute="_compute_max_bookings", default=1, store=True, readonly=False,
        help="""The maximum amount of bookings per slot the appointment can handle (e.g. Allow 6 bookings for the given user/resource).
            This field is only used if the appointment type is not set to manage capacity.""")
    # 'punctual' types are time-bound
    start_datetime = fields.Datetime('Start Datetime')
    end_datetime = fields.Datetime('End Datetime')
    # mail templates
    booked_mail_template_id = fields.Many2one(
        'mail.template', string='Booking Email', ondelete='restrict',
        domain=[('model', '=', 'calendar.attendee')],
        default=_default_booked_mail_template_id,
        help="If set an email will be sent to the customer when the appointment is booked.")
    canceled_mail_template_id = fields.Many2one(
        'mail.template', string='Cancellation Email', ondelete='restrict',
        domain=[('model', '=', 'calendar.event')],
        default=_default_canceled_mail_template_id,
        help="If set an email will be sent to the customer when the appointment is cancelled.")

    # Assignment flow
    assignment_method = fields.Selection([
        ('auto', 'Automatically'),
        ('manual', 'By visitor')],
        string="Assignment", compute="_compute_assignment_method", readonly=False,
        help="How users and resources will be assigned to the meetings that customers book on your website.")
    is_auto_assign = fields.Boolean('Assign automatically')
    is_date_first = fields.Boolean('Select date and time first')
    select_first = fields.Selection([
        ('date', 'Date'),
        ('user_resource', 'User / Resource')],
        string="Starts with", compute="_compute_select_first", readonly=False,
        help="What is selected first by the customer when booking an appointment.")

    category = fields.Selection([
        ('recurring', 'Weekly Schedule'),
        ('punctual', 'Date-limited'),
        ('custom', 'Flexible Schedule'),
        ('anytime', 'Calendar Link')],
        string="Category", compute="_compute_category", inverse="_inverse_category", store="True",
        help="""Used to define this appointment type's category.\n
        Can be one of:\n
            - Weekly Schedule: the default category, weekly recurring slots. Accessible from the website\n
            - Date-limited: regular slots limited between 2 datetimes. Accessible from the website\n
            - Flexible Schedule: the user will create and share to another user a custom appointment type with hand-picked time slots\n
            - Calendar Link: the user will create and share to another user an appointment type covering all their time slots""")
    category_slot_scheduling = fields.Selection(
        [('weekly', 'Weekly'), ('flexible', 'Flexible')],
         string="Schedule", readonly=False, compute="_compute_category_slot_scheduling"
    )
    category_time_display = fields.Selection([
        ('recurring_fields', 'Within the next'),
        ('punctual_fields', 'On specific dates')],
        string="Displayed category time fields", compute="_compute_category_time_display", readonly=False)
    country_ids = fields.Many2many(
        'res.country', 'appointment_type_country_rel', string='Allowed Countries',
        help="Keep empty to allow visitors from any country, otherwise you only allow visitors from selected countries")

    # Frontend Settings
    message_confirmation = fields.Html('Confirmation Message', translate=True,
        help="Extra information provided once the appointment is booked.")
    message_intro = fields.Html('Introduction Message', translate=True,
        sanitize_attributes=False,
        help="Small description of the appointment type.")

    # Display Settings
    hide_duration = fields.Boolean('Hide Duration')
    hide_timezone = fields.Boolean('Hide Time Zone')
    show_avatars = fields.Boolean('Display pictures',
        compute='_compute_show_avatars', readonly=False, store=True,
        help="""Display user or resource images across the entire booking flow.""")

    # Scheduling Configuration
    min_cancellation_hours = fields.Float('Cancel Before (hours)', required=True, default=1.0)
    min_schedule_hours = fields.Float('Schedule before (hours)', required=True, default=1.0)
    max_schedule_days = fields.Integer('Schedule not after (days)', required=True, default=15)

    question_ids = fields.Many2many(
        'appointment.question',
        relation='appointment_type_appointment_question_rel',
        string='Questions',
        default=_default_question_ids)
    reminder_ids = fields.Many2many(
        'calendar.alarm', string="Reminders",
        default=lambda self: self.env['calendar.alarm'].search([('default_for_new_appointment_type', '=', True)]))
    schedule_based_on = fields.Selection([
        ('users', 'Users'),
        ('resources', 'Resources')],
        string="Book", default="users", required=True)
    slot_ids = fields.One2many('appointment.slot', 'appointment_type_id', 'Availabilities', copy=True)
    slot_creation_interval = fields.Float('Create slot every', default=1.0,
        help="Starting from the beginning of the time slot, Odoo will create a new slot at regular intervals based on the time specified here.")

    # Staff Users Management
    staff_user_ids = fields.Many2many(
        'res.users',
        'appointment_type_res_users_rel',
        domain="[('share', '=', False)]",
        string="Users", default=lambda self: self.env.user,
        compute="_compute_staff_user_ids", store=True, readonly=False, tracking=True)
    staff_user_count = fields.Integer('# Staff Users', compute='_compute_staff_user_count')
    user_capacity = fields.Integer('User Capacity', default=1,
        help="The maximum amount of capacity a user can handle when manage capacity is enabled.")

    # Resources Management
    resource_ids = fields.Many2many('appointment.resource', string="Resources",
        relation="appointment_type_appointment_resource_rel",
        compute="_compute_resource_ids", store=True, readonly=False, tracking=True)
    resource_count = fields.Integer('# Resources', compute='_compute_resource_info')
    resource_total_capacity = fields.Integer('Total Capacity', compute="_compute_resource_info")

    # Statistics / Technical / Misc
    appointment_count = fields.Integer('# Appointments', compute='_compute_appointment_counts')
    appointment_count_request = fields.Integer('# Appointments To Confirm', compute="_compute_appointment_counts")
    appointment_count_upcoming = fields.Integer('# Upcoming Appointments', compute='_compute_appointment_counts')
    appointment_invite_ids = fields.Many2many('appointment.invite', string='Invitation Links', copy=False)
    appointment_invite_count = fields.Integer('# Invitation Links', compute='_compute_appointment_invite_count')
    meeting_ids = fields.One2many('calendar.event', 'appointment_type_id', string="Appointment Meetings")

    # Onboarding connectors display (see o_appointment_cal_sync_alert)
    connectors_displayed = fields.Boolean(compute="_compute_connectors_displayed")
    # Technical field for backward compatibility with previous default published appointment type
    is_published = fields.Boolean('Is Published')

    _check_manual_confirmation_percentage = models.Constraint(
        'check(manual_confirmation_percentage >= 0 and manual_confirmation_percentage <= 1)',
        "The capacity percentage should be between 0 and 100%",
    )

    _check_capacity_positive = models.Constraint(
        'check(user_capacity >= 1 AND max_bookings >= 1)',
        'Capacity should be at least 1.',
    )

    @api.depends('meeting_ids')
    def _compute_appointment_counts(self):
        mapped_status_data = {}
        allowed_events = {}
        status_data = self.env['calendar.event']._read_group(
            [('appointment_type_id', 'in', self.ids)],
            ['appointment_type_id', 'appointment_status'], ['__count', 'id:array_agg']
        )
        for appointment_type, status, count, event_ids in status_data:
            if appointment_type.id not in mapped_status_data:
                mapped_status_data[appointment_type.id] = {}
            mapped_status_data[appointment_type.id][status] = count
            allowed_events.setdefault(appointment_type.id, set()).update(event_ids)

        mapped_upcoming_data = {
            # For performance reasons, we add sudo() to bypass record rules and private field domain
            # since they were already validated in the previous _read_group.
            # Security is ensured by taking intersection with previously validated events.
            appointment_type.id: len(set(event_ids) & allowed_events[appointment_type.id])
            for appointment_type, event_ids in self.env['calendar.event'].sudo()._read_group(
                domain=[
                    ('appointment_type_id', 'in', mapped_status_data.keys()),
                    ('start', '>', datetime.now()),
                ],
                groupby=['appointment_type_id'],
                aggregates=['id:array_agg'],
            )
        }
        for appointment_type in self:
            appointment_status_data = mapped_status_data.get(appointment_type.id, {'booked': 0})
            appointment_type.appointment_count = sum(appointment_status_data.values())
            appointment_type.appointment_count_request = appointment_status_data.get('request', 0)
            appointment_type.appointment_count_upcoming = mapped_upcoming_data.get(appointment_type.id, 0)

    @api.depends('appointment_duration')
    def _compute_appointment_duration_formatted(self):
        """
        When appointment duration exceeds a day or is not a multiple of hours e.g., 2 hours 30 minutes,
        it is not fitting in one line, thus we are now using shorter time format.
        E.g., Default (long) format: 2 hours 30 minutes
              Short format: 2 hr 30 min
        """
        for record in self:
            record.appointment_duration_formatted = self.env['ir.qweb.field.duration'].value_to_html(
                record.appointment_duration * 3600,
                {} if record.appointment_duration % 1 == 0 and record.appointment_duration < 24 else {'format': 'short'}
            )

    @api.depends('appointment_invite_ids')
    def _compute_appointment_invite_count(self):
        appointment_data = self.env['appointment.invite']._read_group(
            [('appointment_type_ids', 'in', self.ids)],
            ['appointment_type_ids'],
            ['__count'],
        )
        mapped_data = {appointment_type.id: count for appointment_type, count in appointment_data}
        for appointment_type in self:
            appointment_type.appointment_invite_count = mapped_data.get(appointment_type.id, 0)

    @api.depends('is_auto_assign')
    def _compute_assignment_method(self):
        for appointment in self:
            appointment.assignment_method = 'auto' if appointment.is_auto_assign else 'manual'

    @api.onchange('assignment_method')
    def _onchange_assignment_method(self):
        for appointment in self:
            appointment.is_auto_assign = appointment.assignment_method == 'auto'

    @api.depends('category')
    def _compute_show_avatars(self):
        """ By default, enable avatars for custom appointment types and hide them for recurring and punctual category ones."""
        for record in self:
            record.show_avatars = record.category not in ['punctual', 'recurring']

    @api.depends('start_datetime', 'end_datetime')
    def _compute_category(self):
        for appointment_type in self.filtered(lambda apt: apt.category != 'custom'):
            appointment_type.category = 'punctual' if appointment_type.start_datetime or appointment_type.end_datetime else 'recurring'
            if not appointment_type.slot_ids:
                appointment_type.slot_ids = appointment_type._get_default_slots(appointment_type.category)

    def _inverse_category(self):
        """ Generate the default slots for the anytime appointment types.
        If the category is 'custom', remove irrelevant slots and set punctual fields to False. """
        for appointment_type in self:
            if appointment_type.category == 'anytime':
                appointment_type.slot_ids = appointment_type._get_default_slots('anytime')
            if appointment_type.category == 'custom':
                appointment_type.slot_ids -= appointment_type.slot_ids.filtered(
                    lambda slot: not (slot.start_datetime and slot.end_datetime)
                )
                appointment_type.update({
                    'start_datetime': False,
                    'end_datetime': False,
                })

    @api.depends('category')
    def _compute_category_slot_scheduling(self):
        for apt in self:
            apt.category_slot_scheduling = 'flexible' if apt.category == 'custom' else 'weekly'

    @api.onchange('category_slot_scheduling')
    def _onchange_category_slot_scheduling(self):
        for apt in self.filtered(lambda apt: apt.category != 'anytime'):
            apt.category = (
                'custom' if apt.category_slot_scheduling == 'flexible' else
                'punctual' if apt.start_datetime or apt.end_datetime else
                'recurring'
            )
            if apt.category != 'custom':
                apt.slot_ids = apt._get_default_slots(apt.category)
            else:
                apt.slot_ids = False

    @api.depends('category')
    def _compute_category_time_display(self):
        for appointment_type in self:
            appointment_type.category_time_display = 'punctual_fields' if appointment_type.category == 'punctual' else 'recurring_fields'

    @api.onchange('category_time_display')
    def _onchange_category_time_display(self):
        if self.category_time_display == 'recurring_fields':
            self.update({
                'start_datetime': False,
                'end_datetime': False,
            })

    @api.depends('location_id')
    def _compute_location(self):
        """Use location_id if available, otherwise its name, finally ''. """
        for record in self:
            if (record.location_id.contact_address or '').strip():
                record.location = ', '.join(
                    frag.strip()
                    for frag in record.location_id.contact_address.split('\n') if frag.strip()
                )
            else:
                record.location = record.location_id.name or ''

    @api.depends('auto_confirm', 'manual_confirmation_percentage')
    def _compute_is_always_confirm(self):
        for appointment_type in self:
            appointment_type.is_always_confirm = (
                appointment_type.auto_confirm and
                float_compare(appointment_type.manual_confirmation_percentage, 1.0, 3) == 0
            )

    @api.depends('schedule_based_on')
    def _compute_resource_ids(self):
        for appointment_type in self.filtered(lambda appt: appt.schedule_based_on == 'users'):
            appointment_type.resource_ids = False

    def _compute_connectors_displayed(self):
        connectors_enabled = not self._get_calendars_already_setup() and self._get_calendars_possible_to_setup()
        for appointment_type in self:
            appointment_type.connectors_displayed = (
                connectors_enabled and
                appointment_type.schedule_based_on == 'users' and
                appointment_type.env.user in self.staff_user_ids
            )

    @api.depends('is_date_first')
    def _compute_select_first(self):
        for appointment in self:
            appointment.select_first = 'date' if appointment.is_date_first else 'user_resource'

    @api.onchange('select_first')
    def _onchange_select_first(self):
        for appointment in self:
            appointment.is_date_first = appointment.select_first == 'date'

    @api.depends('schedule_based_on')
    def _compute_staff_user_ids(self):
        for appointment_type in self.filtered(lambda appt: appt.schedule_based_on == 'resources'):
            appointment_type.staff_user_ids = False

    @api.depends('resource_ids', 'resource_ids.capacity')
    def _compute_resource_info(self):
        resource_data = self.env['appointment.resource']._read_group(
            [('appointment_type_ids', 'in', self.ids)],
            ['appointment_type_ids'],
            ['__count', 'capacity:sum'])
        mapped_data = {
            appointment_type.id: {
                'count': count,
                'total_capacity': total_capacity,
            } for appointment_type, count, total_capacity in resource_data}

        for appointment_type in self:
            if not appointment_type.id:  # new record
                appointment_type.resource_count = len(appointment_type.resource_ids)
                appointment_type.resource_total_capacity = sum(resource.capacity for resource in appointment_type.resource_ids)
            else:
                appointment_type_data = mapped_data.get(appointment_type.id, {})
                appointment_type.resource_count = appointment_type_data.get('count', 0)
                appointment_type.resource_total_capacity = appointment_type_data.get('total_capacity', 0)

    @api.depends('staff_user_ids')
    def _compute_staff_user_count(self):
        for record in self:
            record.staff_user_count = len(record.staff_user_ids)

    @api.depends('manage_capacity')
    def _compute_max_bookings(self):
        for appointment_type in self:
            if appointment_type.manage_capacity:
                appointment_type.max_bookings = 1

    @api.constrains('category', 'start_datetime', 'end_datetime')
    def _check_appointment_category_time_boundaries(self):
        for appointment_type in self:
            if appointment_type.category == 'punctual' and not (appointment_type.start_datetime and appointment_type.end_datetime):
                raise ValidationError(_('A punctual appointment type should be limited between a start and end datetime.'))
            elif appointment_type.category != 'punctual' and (appointment_type.start_datetime or appointment_type.end_datetime):
                raise ValidationError(_("A %s appointment type shouldn't be limited by datetimes.", appointment_type.category))
            if appointment_type.start_datetime and appointment_type.end_datetime and appointment_type.start_datetime > appointment_type.end_datetime:
                raise ValidationError(_("Start date should precede the end date."))

    @api.constrains('appointment_duration')
    def _check_appointment_duration(self):
        for record in self:
            if not record.appointment_duration > 0.0:
                raise ValidationError(_('Appointment Duration should be higher than 0.00.'))

    @api.constrains('category', 'staff_user_ids', 'schedule_based_on')
    def _check_staff_user_configuration(self):
        anytime_appointments = self.search([('category', '=', 'anytime')])
        for appointment_type in self.filtered(lambda appt: appt.schedule_based_on == "users" and appt.category == "anytime"):
            duplicate = anytime_appointments.filtered(lambda apt_type: bool(apt_type.staff_user_ids & appointment_type.staff_user_ids))
            if appointment_type.ids != duplicate.ids:
                raise ValidationError(_("Only one anytime appointment type is allowed for a specific user."))

    def _can_return_content(self, field_name=None, access_token=None):
        """Give the public users access to the unpublished appointment types images when they have an invitation link."""
        if field_name in ["image_%s" % size for size in [1920, 1024, 512, 256, 128]]:
            return True
        return super()._can_return_content(field_name, access_token)

    @api.model_create_multi
    def create(self, vals_list):
        """ We don't want the current user to be follower of all created types """
        return super(AppointmentType, self.with_context(mail_create_nosubscribe=True)).create(vals_list)

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [dict(
            vals,
            name=self.env._("%s (copy)", appointment_type.name),
            category=appointment_type.category,
        ) for appointment_type, vals in zip(self, vals_list)]

    def action_calendar_event_view_request(self):
        action = self.action_calendar_meetings(calendar_event_domain=[('appointment_status', '=', 'request')])
        action['context'].update({
            'search_default_filter_appointment_status_request': True,
            'default_start_date': action['context']['initial_date'],
        })
        return action

    def action_calendar_meetings(self, calendar_event_domain=False):
        self.ensure_one()
        if self.schedule_based_on == 'users':
            action = self.env["ir.actions.actions"]._for_xml_id("appointment.calendar_event_action_view_bookings_users")
        else:
            action = self.env["ir.actions.actions"]._for_xml_id("appointment.calendar_event_action_view_bookings_resources")
        domain = Domain('start', '>=', datetime.today())
        if calendar_event_domain:
            domain &= Domain(calendar_event_domain)
        appointments = self.meeting_ids.filtered_domain(domain)
        nbr_appointments_week_later = appointments.filtered_domain([
            ('start', '>=', datetime.today() + timedelta(weeks=1))
        ])

        # Add and reorder views
        action = AppointmentType.insert_reorder_action_views(action, ['gantt', 'calendar'])

        action['context'] = ast.literal_eval(action['context'])
        action['context'].update({
            'default_scale': self._get_gantt_scale(),
            'default_appointment_type_id': self.id,
            'default_duration': self.appointment_duration,
            'default_partner_ids': [],
            'search_default_appointment_type_id': self.id,
            'default_mode': "month" if nbr_appointments_week_later else "week",
            'initial_date': appointments[0].start if appointments else datetime.today(),
            'default_start_date': datetime.today(),  # gantt view
        })
        return action

    @api.model
    def action_calendar_meetings_resources_all(self):
        action = self.env["ir.actions.actions"]._for_xml_id("appointment.calendar_event_action_view_bookings_resources")
        action['context'] = ast.literal_eval(action['context'])
        action['context'].update({
            'default_scale': self.search([('schedule_based_on', '=', 'resources')])._get_gantt_scale(),
        })
        action['path'] = 'resource-bookings'
        return action

    @api.model
    def action_calendar_meetings_users_all(self):
        action = self.env["ir.actions.actions"]._for_xml_id("appointment.calendar_event_action_view_bookings_users")
        action = AppointmentType.insert_reorder_action_views(action, ['gantt'])
        action['context'] = ast.literal_eval(action['context'])
        action['context'].update({
            'default_scale': self.search([('schedule_based_on', '=', 'users')])._get_gantt_scale(),
        })
        action['path'] = 'staff-bookings'
        return action

    def action_share_invite(self):
        return {
            'name': _('Create a Share Link'),
            'type': 'ir.actions.act_window',
            'res_model': 'appointment.invite',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_appointment_type_ids': self.ids,
                'dialog_size': 'medium',
            }
        }

    def action_customer_preview(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': url_join(self.get_base_url(), '/appointment/%s' % self.id),
            'target': 'self',
        }

    def get_kanban_record_share_btn_url(self):
        self.ensure_one()
        existing_invitation = self.env['appointment.invite']._find_identical_config(self.ids, 'all_assigned_resources')
        if existing_invitation:
            return existing_invitation.book_url

        return self.env['appointment.invite'].create([{
            'appointment_type_ids': self.ids,
            'resources_choice': 'all_assigned_resources'
        }]).book_url

    # --------------------------------------
    # View Utils
    # --------------------------------------

    @staticmethod
    def insert_reorder_action_views(action, first_view_names):
        """Set the first N entries in views_ids of an action dict reusing existing views.

        :param dict action: Dict representing an action.
        :param list[str] first_view_names: List of the names of the first N views.
        :return: The original action, with view_mode and view_ids modified.
        :rtype: dict
        """
        existing_views = [view for view in action["view_mode"].split(',') if view not in first_view_names]
        action['view_mode'] = ",".join(first_view_names + existing_views)
        for view_type in reversed(first_view_names):
            to_insert = (False, view_type)
            try:
                existing_view_id = next(index for index, view_tuple
                                        in enumerate(action['views'])
                                        if view_tuple[1] == view_type)
                to_insert = action['views'].pop(existing_view_id)
            except StopIteration:
                pass
            action['views'].insert(0, to_insert)
        return action

    @api.model
    def _get_calendars_already_setup(self):
        return []

    @api.model
    def _get_calendars_possible_to_setup(self):
        return []

    def _get_gantt_scale(self):
        """Return the default scale to show related meetings in gantt.

        The idea is to show a relevant time frame based on available meetings.
        For example: if the last available meeting is the same week as "now", no need to show an entire year, a week will suffice.
        """
        now = datetime.utcnow()
        last_meeting_values = self.env['calendar.event'].search_read([
            ('appointment_type_id', 'in', self.ids),
            ('appointment_resource_ids', '!=', False),
            ('stop', '>=', now.date()),
        ], ['stop'], limit=1, order='stop desc')
        last_meeting_end = last_meeting_values[0]['stop'] if last_meeting_values else False
        if not last_meeting_end or now.date() == last_meeting_end.date():
            return 'day'
        same_year = now.year == last_meeting_end.year
        same_month = now.month == last_meeting_end.month
        same_week = now.isocalendar().week == last_meeting_end.isocalendar().week
        if same_year and same_month and same_week:
            return 'week'
        if same_year and same_month:
            return 'month'
        return 'year'

    def _get_main_phone_question(self):
        self.ensure_one()
        return next((q for q in self.question_ids if q.question_type == 'phone'), self.env['appointment.question'])

    def _get_placeholder_filename(self, field):
        return 'appointment/static/src/img/appointment_cover_0.jpg'

    # --------------------------------------
    # Slots Generation
    # --------------------------------------

    @api.model
    def _get_default_slots(self, category):
        range_values = self._get_default_range_slots(category)
        return [
            Command.create({
                'weekday': str(weekday),
                'start_hour': start_hour,
                'end_hour': end_hour
            })
            for weekday in range(*range_values['weekday_range'])
            for (start_hour, end_hour) in range_values['hours_range']
        ]

    def _get_default_range_slots(self, category):
        '''
            If the appointment type is of category recurring or punctual, we set the arbitrary 'standard'
            appointment slots range (from monday to friday, 9AM-12PM and 2PM-5PM).
            If the appointment type is of category anytime, we set the slots range
            as any time between 2 arbitrary hours (monday to sunday, 7AM-7PM).
            The slot range for the anytime category will be updated in appointment_hr
            to match the user work hours.
        '''
        if category not in ['punctual', 'recurring', 'anytime']:
            raise ValueError(_("Default slots cannot be applied to the %s appointment type category.", category))
        if category in ['punctual', 'recurring']:
            weekday_range = (1, 6)
            hours_range = ((9, 12), (14, 17))
        else:
            weekday_range = (1, 8)
            hours_range = ((7, 19),)
        return {
            'weekday_range': weekday_range,
            'hours_range': hours_range,
        }

    def _get_default_appointment_status(self, start_dt, stop_dt, capacity_reserved):
        """ Get the status of the appointment based on users/resources and the auto confirm option.
        :param datetime start_dt: start datetime of appointment (in naive UTC)
        :param datetime stop_dt: stop datetime of appointment (in naive UTC)
        :param int capacity_reserved: capacity reserved by the customer for the appointment
        """
        self.ensure_one()
        default_state = 'booked'
        if not self.is_always_confirm:
            if not self.auto_confirm:
                default_state = 'request'
            else:
                bookings_data = self.env['appointment.booking.line'].sudo()._read_group([
                    ('appointment_type_id', '=', self.id),
                    ('event_start', '<', stop_dt),
                    ('event_stop', '>', start_dt)
                ], [], ['capacity_used:sum'])
                capacity_already_used = bookings_data[0][0]

                if self.manage_capacity:
                    total_capacity = (
                        self.resource_total_capacity if self.schedule_based_on == 'resources' else
                        len(self.staff_user_ids) * self.user_capacity)
                else:
                    total_capacity = (
                        len(self.resource_ids) * self.max_bookings if self.schedule_based_on == 'resources' else
                        len(self.staff_user_ids) * self.max_bookings)

                total_capacity_used = capacity_already_used + capacity_reserved
                if float_compare(total_capacity_used / total_capacity, self.manual_confirmation_percentage, 2) > 0:
                    default_state = 'request'
        return default_state

    def _slots_generate(self, first_day, last_day, timezone, reference_date=None):
        """ Generate all appointment slots (in naive UTC, appointment timezone, and given (visitors) timezone)
            between first_day and last_day

        :param datetime first_day: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime last_day: end of appointment check boundary. Timezoned to UTC;
        :param str timezone: requested timezone string e.g.: 'Europe/Brussels' or 'Etc/GMT+1'
        :param datetime reference_date: starting datetime to fetch slots (in naive UTC). If not
          given now (in naive UTC) is used instead. Note that minimum schedule hours
          defined on appointment type is added to the beginning of slots if the
          slot start is too close from now;

        :return: [ {'slot': slot_record, <timezone>: (date_start, date_end), ...},
                  ... ]
        """
        if not reference_date:
            reference_date = datetime.utcnow()
        appt_tz = pytz.timezone(self.appointment_tz)
        requested_tz = pytz.timezone(timezone)
        end_tz_apt_type = self.end_datetime.astimezone(appt_tz) if self.category == 'punctual' else False
        ref_tz_apt_type = reference_date.astimezone(appt_tz)
        now_tz_apt_type = datetime.utcnow().astimezone(appt_tz)
        slots = []

        # Considering:
        #   - Now = 9AM
        #   - Min schedule hours = 1 hour
        #   - Reference datetime = now (recurring / anytime / punctual with start in the past)
        #                          or a datetime in the future (punctual with start in the future).
        # If the reference datetime is <= now + min (meaning between 9AM and 10AM) then
        # we need to add the min schedule hours to the beginning of first slot (the reference datetime).
        # Otherwise no need to add it as min schedule hours isn't needed when the start is far enough in the future.
        ref_start = ref_tz_apt_type
        if ref_start <= (now_tz_apt_type + relativedelta(hours=self.min_schedule_hours)):
            ref_start += relativedelta(hours=self.min_schedule_hours)

        def append_slot(day, slot):
            """ Appends and generates all recurring slots. In case day is the
            reference date we adapt local_start to not append slots in the past.
            e.g. With a slot duration of 1 hour if we have slots from 8:00 to
            17:00 and we are now 9:30 for today. The first slot that we append
            should be 11:00 and not 8:00. This is necessary since we no longer
            always check based on working hours that were ignoring these past
            slots.

            :param date day: day for which we generate slots;
            :param record slot: a <appointment.slot> record
            """
            local_start = appt_tz.localize(
                datetime.combine(day,
                                 time(hour=int(slot.start_hour),
                                      minute=int(round((slot.start_hour % 1) * 60))
                                     )
                                )
            )
            # Adapt local start to not append slot in the past from ref
            # Using ref_start to consider or not the min schedule hours at the beginning of first slot
            while local_start < ref_start:
                local_start += relativedelta(hours=self.slot_creation_interval)
            local_end = local_start + relativedelta(hours=self.appointment_duration)
            # localized end time for the entire slot on that day
            local_slot_end = appt_tz.localize(
                day.replace(hour=0, minute=0, second=0) +
                timedelta(hours=slot._convert_end_hour_24_format())
            )
            # Adapt local_slot_end to not append slot if local_slot_end is in the future of the appointment end_datetime
            if end_tz_apt_type and local_start.date() == end_tz_apt_type.date() and local_slot_end > end_tz_apt_type:
                local_slot_end = end_tz_apt_type

            while local_start + relativedelta(hours=self.appointment_duration) <= local_slot_end:
                slots.append({
                    self.appointment_tz: (
                        local_start,
                        local_end,
                    ),
                    timezone: (
                        local_start.astimezone(requested_tz),
                        local_end.astimezone(requested_tz),
                    ),
                    'UTC': (
                        local_start.astimezone(pytz.UTC).replace(tzinfo=None),
                        local_end.astimezone(pytz.UTC).replace(tzinfo=None),
                    ),
                    'slot': slot,
                })
                local_start += relativedelta(hours=self.slot_creation_interval)
                local_end = local_start + relativedelta(hours=self.appointment_duration)
        # We use only the recurring slot if it's not a custom appointment type.
        if self.category != 'custom':

            # Don't generate slots if the appointment boundaries are completely in the past or there is no interval in between the slots.
            if last_day < reference_date.astimezone(pytz.UTC) or self.slot_creation_interval <= 0:
                return slots

            # Regular recurring slots (not a custom appointment), generate necessary slots using configuration rules
            slot_weekday = [int(weekday) - 1 for weekday in self.slot_ids.mapped('weekday')]
            for day in rrule.rrule(rrule.DAILY,
                                dtstart=first_day.astimezone(appt_tz).date(),
                                until=last_day.astimezone(appt_tz).date(),
                                byweekday=slot_weekday):
                for slot in self.slot_ids.filtered(lambda x: int(x.weekday) == day.isoweekday()):
                    append_slot(day, slot)
        else:
            # Custom appointment type, we use "unique" slots here that have a defined start/end datetime
            # We compare it with ref_start (which is localized here, so we adapt slot start_datetime to compare)
            unique_slots = self.slot_ids.filtered(
                lambda slot: slot.slot_type == 'unique' and slot.start_datetime.astimezone(appt_tz) > ref_start
            )

            for slot in unique_slots:
                start = slot.start_datetime.astimezone(tz=None)
                end = slot.end_datetime.astimezone(tz=None)
                startUTC = start.astimezone(pytz.UTC).replace(tzinfo=None)
                endUTC = end.astimezone(pytz.UTC).replace(tzinfo=None)
                slots.append({
                    self.appointment_tz: (
                        start.astimezone(appt_tz),
                        end.astimezone(appt_tz),
                    ),
                    timezone: (
                        start.astimezone(requested_tz),
                        end.astimezone(requested_tz),
                    ),
                    'UTC': (
                        startUTC,
                        endUTC,
                    ),
                    'slot': slot,
                })
        return slots

    def _get_appointment_slots(self, timezone, filter_users=None, filter_resources=None, asked_capacity=1, reference_date=None):
        """ Fetch available slots to book an appointment.

        :param str timezone: timezone string e.g.: 'Europe/Brussels' or 'Etc/GMT+1'
        :param <res.users> filter_users: filter available slots for those users (can be a singleton
          for fixed appointment types or can contain several users, e.g. with random assignment and
          filters) If not set, use all users assigned to this appointment type.
        :param <appointment.resource> filter_resources: filter available slots for those resources
          (can be a singleton for fixed appointment types or can contain several resources,
          e.g. with random assignment and filters) If not set, use all resources assigned to this
          appointment type.
        :param int asked_capacity: the capacity the user want to book.
        :param datetime reference_date: starting datetime to fetch slots. If not
          given now (in UTC) is used instead. Note that minimum schedule hours
          defined on appointment type is added to the beginning of slots;

        :returns: list of dicts (1 per month) containing available slots per week
          and per day for each week (see ``_slots_generate()``), like
          [
            {'id': 0,
             'month': 'February 2022' (formatted month name),
             'weeks': [
                [{'day': '']
                [{...}],
             ],
            },
            {'id': 1,
             'month': 'March 2022' (formatted month name),
             'weeks': [ (...) ],
            },
            {...}
          ]
        """
        self.ensure_one()

        if not self.active:
            return []
        now = datetime.utcnow()
        if not reference_date:
            reference_date = now

        try:
            requested_tz = pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            requested_tz = self.appointment_tz

        appointment_duration_days = self.max_schedule_days
        unique_slots = self.slot_ids.filtered(lambda slot: slot.slot_type == 'unique')

        if self.category == 'custom' and unique_slots:
            # Custom appointment type, the first day is the earliest slot start if in the future, else now
            start_first_slot = unique_slots[0].start_datetime
            first_day = requested_tz.fromutc(start_first_slot if reference_date < start_first_slot else reference_date)
            last_day = requested_tz.fromutc(max(unique_slots.mapped('end_datetime')))
        elif self.category == 'punctual':
            # Punctual appointment type, the first day is the start_datetime if it is in the future, else the first day is now
            first_day = requested_tz.fromutc(self.start_datetime if self.start_datetime > now else now)
            last_day = requested_tz.fromutc(self.end_datetime)
        else:
            # Recurring appointment type
            first_day = requested_tz.fromutc(reference_date + relativedelta(hours=self.min_schedule_hours))
            last_day = requested_tz.fromutc(reference_date + relativedelta(days=appointment_duration_days))

        # Compute available slots (ordered)
        slots = self._slots_generate(
            first_day.astimezone(pytz.utc),
            last_day.astimezone(pytz.utc),
            timezone,
            reference_date=reference_date
        )

        # No slots -> skip useless computation
        if not slots:
            return slots
        valid_users = filter_users.filtered(lambda user: user in self.staff_user_ids) if filter_users else None
        valid_resources = filter_resources.filtered(lambda resource: resource in self.resource_ids) if filter_resources else None
        # Not found staff user : incorrect configuration -> skip useless computation
        if filter_users and not valid_users:
            return []
        if filter_resources and not valid_resources:
            return []
        # Used to check availabilities for the whole last day as _slot_generate will return all slots on that date.
        last_day_end_of_day = datetime.combine(
            last_day.astimezone(pytz.timezone(self.appointment_tz)),
            time.max
        )
        if self.schedule_based_on == 'users':
            self._slots_fill_users_availability(
                slots,
                first_day.astimezone(pytz.UTC),
                last_day_end_of_day.astimezone(pytz.UTC),
                valid_users,
                asked_capacity,
            )
            slot_field_label = 'available_staff_users' if not self.is_auto_assign and self.is_date_first else 'staff_user_id'
        else:
            self._slots_fill_resources_availability(
                slots,
                first_day.astimezone(pytz.UTC),
                last_day_end_of_day.astimezone(pytz.UTC),
                valid_resources,
                asked_capacity,
            )
            slot_field_label = 'available_resource_ids'

        total_nb_slots = sum(slot_field_label in slot for slot in slots)
        # If there is no slot for the minimum capacity then we return an empty list.
        # This will lead to a screen informing the customer that there is no availability.
        # We don't want to return an empty list if the capacity as been tempered by the customer
        # as he should still be able to interact with the screen and select another capacity.
        if not total_nb_slots and asked_capacity == 1:
            return []

        # Compute calendar rendering and inject available slots
        today = requested_tz.fromutc(reference_date)
        start = slots[0][timezone][0] if slots else today
        locale = babel_locale_parse(get_lang(self.env).code)
        month_dates_calendar = cal.Calendar(locale.first_week_day).monthdatescalendar
        months = []
        while (start.year, start.month) <= (last_day.year, last_day.month):
            has_availabilities = False
            dates = month_dates_calendar(start.year, start.month)
            for week_index, week in enumerate(dates):
                for day_index, day in enumerate(week):
                    mute_cls = weekend_cls = today_cls = None
                    today_slots = []
                    if day.weekday() in (locale.weekend_start, locale.weekend_end):
                        weekend_cls = 'o_weekend bg-light'
                    if day == today.date() and day.month == today.month:
                        today_cls = 'o_today'
                    if day.month != start.month:
                        mute_cls = 'd-none'
                    else:
                        tz = self.appointment_tz if slots and slots[0]['slot'].allday else timezone
                        # slots are ordered, so check all unprocessed slots from until > day
                        while slots and (slots[0][tz][0].date() <= day):
                            is_allday = slots[0]['slot'].allday
                            tz = self.appointment_tz if is_allday else timezone
                            if (slots[0][tz][0].date() == day) and (slot_field_label in slots[0]):
                                slot_start_dt_tz, slot_end_dt_tz = slots[0][tz]
                                slot_start_dt_tz_formatted = slot_start_dt_tz.strftime('%Y-%m-%d %H:%M:%S')
                                slot_duration = slots[0]['slot'].duration or str((slot_end_dt_tz - slot_start_dt_tz).total_seconds() / 3600)
                                # Remove one second in case the end time slot reached midnight of the next day
                                # e.g. 6PM (June 1st) to 12AM (June 2nd) should not be considered as a multi day slot
                                is_multi_day = (
                                    slot_start_dt_tz.date() != (slot_end_dt_tz - timedelta(seconds=1)).date()
                                ) if not is_allday else slot_duration > 24
                                slot = {
                                    'available_resources': [{
                                        'id': resource.id,
                                        'name': resource.name,
                                        'capacity': resource.capacity,
                                    } for resource in slots[0]['available_resource_ids']] if self.schedule_based_on == 'resources' else False,
                                    'datetime': slot_start_dt_tz_formatted,
                                }
                                if self.schedule_based_on == 'users' and not self.is_auto_assign and self.is_date_first:
                                    slot.update({'available_staff_users': [{
                                        'id': staff.id,
                                        'name': staff.name,
                                    } for staff in slots[0]['available_staff_users']]})
                                elif self.schedule_based_on == 'users':
                                    slot.update({'staff_user_id': slots[0]['staff_user_id'].id})

                                start_date = format_datetime(slot_start_dt_tz, format='EEE d', locale=locale)
                                end_date = format_datetime(slot_end_dt_tz, format='EEE d', locale=locale)
                                start_hour = format_time(slot_start_dt_tz.time(), format='short', locale=locale)
                                end_hour = format_time(slot_end_dt_tz.time(), format='short', locale=locale)
                                if is_multi_day:
                                    slot_start_formatted = start_date
                                    slot_end_formatted = end_date
                                    if not is_allday:
                                        slot_start_formatted = f"{slot_start_formatted} - {start_hour}"
                                        slot_end_formatted = f"{slot_end_formatted} - {end_hour}"
                                elif is_allday:
                                    slot_start_formatted = _("All day")
                                    slot_end_formatted = False
                                else:
                                    slot_start_formatted = start_hour
                                    slot_end_formatted = end_hour if self.category == 'custom' else False
                                slot.update({
                                    'end_hour': slot_end_formatted,
                                    'is_long_duration': is_multi_day or is_allday,
                                    'slot_duration': slot_duration,
                                    'start_hour': slot_start_formatted,
                                })

                                url_parameters = {
                                    'allday': int(is_allday),
                                    'date_time': slot_start_dt_tz_formatted,
                                    'duration': slot_duration,
                                }
                                if self.schedule_based_on == 'users' and not (self.is_date_first and not self.is_auto_assign):
                                    url_parameters.update(staff_user_id=str(slots[0]['staff_user_id'].id))
                                elif self.schedule_based_on == 'resources':
                                    url_parameters.update(available_resource_ids=str(slots[0]['available_resource_ids'].ids))
                                slot['url_parameters'] = url_encode(url_parameters)
                                today_slots.append(slot)
                            slots.pop(0)
                    today_slots = sorted(today_slots, key=lambda d: (not d['is_long_duration'], d['datetime']))
                    dates[week_index][day_index] = {
                        'day': day,
                        'slots': today_slots,
                        'mute_cls': mute_cls,
                        'weekend_cls': weekend_cls,
                        'today_cls': today_cls
                    }

                    has_availabilities = has_availabilities or bool(today_slots)

            months.append({
                'id': len(months),
                'month': format_datetime(start, 'MMMM Y', locale=get_lang(self.env).code),
                'weeks': dates,
                'has_availabilities': has_availabilities,
            })
            start = start + relativedelta(months=1)
        return months

    def _check_appointment_is_valid_slot(self, staff_user, resources, asked_capacity, timezone, start_dt, duration, allday):
        """
        Given slot parameters check if it is still valid, based on employee
        availability, slot boundaries, ...
        :param (optional record) staff_user: the user for whom the appointment was booked for
        :param (optional record) resources: the resources for which the appointment was booked for
        :param integer asked_capacity: the capacity asked by the customer
        :param str timezone: visitor's timezone
        :param datetime start_dt: start datetime of the appointment (UTC)
        :param float duration: the duration of the appointment in hours
        :param int allday: if the slot is for allday
        :return: True if at least one slot is available, False if no slots were found
        """
        # the user can be a public/portal user that doesn't have read access to the appointment_type.
        self_sudo = self.sudo()
        end_dt = start_dt + relativedelta(hours=duration)
        if allday:
            # Remove a day if allday to have the same settings of dates as meetings for allday
            end_dt -= relativedelta(days=1)
        slots = self_sudo._slots_generate(start_dt, end_dt, timezone)
        slots = [slot for slot in slots if slot['UTC'] == (start_dt.replace(tzinfo=None), end_dt.replace(tzinfo=None))]
        if slots and self_sudo.schedule_based_on == 'users' and (not staff_user or staff_user in self_sudo.staff_user_ids):
            self_sudo._slots_fill_users_availability(slots, start_dt, end_dt, staff_user)
        elif slots and self_sudo.schedule_based_on == 'resources' and (not resources or all(r in self_sudo.resource_ids for r in resources)):
            self_sudo._slots_fill_resources_availability(slots, start_dt, end_dt, filter_resources=resources, asked_capacity=asked_capacity)
        for slot in slots:
            if (staff_user and
                not (self.is_date_first and not self.is_auto_assign)
                and slot.get("staff_user_id", False) != staff_user
            ):
                continue
            if (staff_user and
                self.is_date_first and not self.is_auto_assign and
                staff_user not in slot.get("available_staff_users", self.env['res.users'])
            ):
                continue
            if resources and any(resource not in slot.get("available_resource_ids", []) for resource in resources):
                continue
            if slot['slot'].slot_type == 'recurring' and float_compare(self_sudo.appointment_duration, duration, 2) != 0:
                continue
            if slot['slot'].slot_type == 'unique' and slot['slot'].duration != round(duration, 2):
                continue
            return True
        return False

    @api.model
    def _get_clean_appointment_context(self):
        whitelist_default_fields = list(map(
            lambda field: f'default_{field}',
            self._get_calendar_view_appointment_type_default_context_fields_whitelist()))
        return {
            key: value for key, value in self.env.context.items()
            if key in whitelist_default_fields or not key.startswith('default_')
        }

    @api.model
    def _get_calendar_view_appointment_type_default_context_fields_whitelist(self):
        """ White list of fields that can be defaulted in the context of the
        calendar routes creating appointment types and invitations.
        This is mainly used in /appointment/appointment_type/create_custom and
        /appointment/appointment_type/search_create_anytime.
        This list of fields can be updated the fields in other sub-modules.
        """
        return []

    def _prepare_calendar_event_values(
        self, asked_capacity, booking_line_values, description, duration, allday,
        appointment_invite, guests, name, customer, staff_user, start, stop
    ):
        """ Returns all values needed to create the calendar event from the values outputed
            by the form submission and its processing. This should be used with values of format
            matching appointment_form_submit controller's ones.

            In case of an allday event, we need to remove a day to the end time to compensate the
            duration that was added during flow and to then match the date consensus of calendar events.
            For example:
                for an allday slot on the 4th May, we should have the 4th May 00:00 for both start and stop
                date instead of 4th May 00:00 -> 5th May 00:00 which would refer to an allday slot of a duration
                of 2 days.
            Also allday slot makes sense only in the timezone of the appointment type to keep the
            specific day that was selected by the staff user.
            ...
            :param list<dict> booking_line_values: create values of booking lines
            :param str name: name filled in form
            :param <res.partner> guests: list of guest partners
            :param res.partner customer: partner who made the booking
            :param dt start: start of picked slot UTC
            :param dt stop: end of picked slot UTC
            :return: dict of values used in create method of calendar event
        """
        self.ensure_one()
        partners = (staff_user.partner_id | customer) if staff_user else customer
        guests = guests or self.env['res.partner']
        appointment_status = self._get_default_appointment_status(start, stop, asked_capacity)
        attendee_values = [Command.create({'partner_id': pid, 'state': 'accepted'}) for pid in partners.ids] + \
            [Command.create({'partner_id': guest.id}) for guest in guests - partners if guest]
        if allday:
            stop -= relativedelta(days=1)
            start = start.astimezone(pytz.timezone(self.appointment_tz)).replace(tzinfo=None)
            stop = stop.astimezone(pytz.timezone(self.appointment_tz)).replace(tzinfo=None)
        return {
            'alarm_ids': [Command.set(self.reminder_ids.ids)],
            'allday': allday,
            'appointment_booker_id': customer.id,
            'appointment_invite_id': appointment_invite.id,
            'appointment_status': appointment_status,
            'appointment_type_id': self.id,
            'attendee_ids': attendee_values,
            'booking_line_ids': [Command.create(vals) for vals in booking_line_values],
            'description': description,
            'duration': duration,
            'location': self.location,
            'name': _('%(attendee_name)s - %(appointment_name)s Booking',
                        attendee_name=name, appointment_name=self.name),
            'partner_ids': [Command.link(pid) for pid in (partners | guests).ids],
            'start': fields.Datetime.to_string(start),
            'start_date': fields.Datetime.to_string(start),
            'stop': fields.Datetime.to_string(stop),
            'stop_date': fields.Datetime.to_string(stop),
            'user_id': staff_user.id if self.schedule_based_on == 'users' else self.create_uid.id,
        }

    # --------------------------------------
    # Staff Users - Slots Availability
    # --------------------------------------

    def _slots_fill_users_availability(self, slots, start_dt, end_dt, filter_users=None, asked_capacity=1):
        """ Fills the slot structure with an available user

        :param list slots: slots (list of slot dict), as generated by ``_slots_generate``;
        :param datetime start_dt: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt: end of appointment check boundary. Timezoned to UTC;
        :param <res.users> filter_users: filter available slots for those users (can be a singleton
          for fixed appointment types or can contain several users e.g. with random assignment and
          filters) If not set, use all users assigned to this appointment type.
        :param int asked_capacity: the amount of capacity user wants to book.

        :return: None but instead update ``slots`` adding ``staff_user_id`` or ``available_staff_users`` key
          containing available user(s);
        """
        # shuffle the available users into a random order to avoid having the same
        # one assigned every time, force timezone
        available_users = [
            user.with_context(tz=user.tz)
            for user in (filter_users or self.staff_user_ids)
        ]
        random.shuffle(available_users)
        available_users_tz = self.env['res.users'].concat(*available_users)

        # fetch value used for availability in batch
        availability_values = self._slot_availability_prepare_users_values(
            available_users_tz, start_dt, end_dt
        )

        for slot in slots:
            if (self.is_date_first and not self.is_auto_assign) or self.env.context.get('slots_check_all_users', False):
                available_staff_users = available_users_tz.filtered(
                    lambda staff_user: self._slot_availability_is_user_available(
                        slot,
                        staff_user,
                        availability_values,
                        asked_capacity,
                    )
                )
            else:
                available_staff_users = next(
                    (staff_user for staff_user in available_users_tz if self._slot_availability_is_user_available(
                        slot,
                        staff_user,
                        availability_values,
                        asked_capacity,
                    )),
                    False)
            if available_staff_users:
                if (self.is_date_first and not self.is_auto_assign) or self.env.context.get('slots_check_all_users', False):
                    slot['available_staff_users'] = available_staff_users
                else:
                    slot['staff_user_id'] = available_staff_users

    def _slot_availability_is_user_available(self, slot, staff_user, availability_values, asked_capacity=1):
        """ This method verifies if the user is available for the given capacity
        on the given slot. It checks whether the user has calendar events clashing
        and if he is included in slot's restricted users.

        Can be overridden to add custom checks.

        :param dict slot: a slot as generated by ``_slots_generate``;
        :param <res.users> staff_user: user to check against slot boundaries.
          At this point timezone should be correctly set in context;
        :param dict availability_values: dict of data used for availability check.
          See ``_slot_availability_prepare_users_values()`` for more details;
        :return: boolean: is user available for an appointment for given slot
        """
        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
        staff_user_tz = pytz.timezone(staff_user.tz) if staff_user.tz else pytz.utc
        slot_start_dt_user_timezone = slot_start_dt_utc.astimezone(staff_user_tz)
        slot_end_dt_user_timezone = slot_end_dt_utc.astimezone(staff_user_tz)

        if slot['slot'].restrict_to_user_ids and staff_user not in slot['slot'].restrict_to_user_ids:
            return False

        if slot['slot'].allday:
            slot_end_dt_utc += relativedelta(days=1)

        users_remaining_capacity = self._get_users_remaining_capacity(staff_user, slot['UTC'][0], slot['UTC'][1],
            users_to_bookings=availability_values.get('users_to_bookings'))
        partner_to_events = availability_values.get('partner_to_events') or {}
        if partner_to_events.get(staff_user.partner_id):
            for day_dt in rrule.rrule(freq=rrule.DAILY,
                                      dtstart=slot_start_dt_utc,
                                      until=slot_end_dt_utc,
                                      interval=1):
                day_events = partner_to_events[staff_user.partner_id].get(day_dt.date()) or []
                for event in day_events:
                    if not event.allday and (event.start < slot_end_dt_utc and event.stop > slot_start_dt_utc):
                        # Skip marking user unavailable for the same appointment type until max capacity
                        if self == event.appointment_type_id \
                            and users_remaining_capacity['total_remaining_capacity'] >= asked_capacity:
                            continue
                        return False
            for day_dt in rrule.rrule(freq=rrule.DAILY,
                                      dtstart=slot_start_dt_user_timezone,
                                      until=slot_end_dt_user_timezone,
                                      interval=1):
                day_events = partner_to_events[staff_user.partner_id].get(day_dt.date()) or []
                if any(event.allday for event in day_events):
                    return False
        return True

    def _get_users_remaining_capacity(self, users, slot_start_utc, slot_stop_utc, users_to_bookings=None, filter_users=None):
        """ Compute the remaining capacities for users in a particular time slot.
            :param <res.users> users : record containing one or a multiple of users
            :param datetime slot_start_utc: start of slot (in naive UTC)
            :param datetime slot_stop_utc: end of slot (in naive UTC)
            :param list users_to_bookings: list of users linked to their booking lines from the prepared value.
                If no value is passed, then we search manually the booking lines (used for the appointment validation step)
            :param <res.users> filter_users: filter the users impacted with this value
            :return: integer: remaining_capacity:
        """
        self.ensure_one()

        all_users = users & self.staff_user_ids
        if filter_users:
            all_users &= filter_users
        if not users:
            return {'total_remaining_capacity': 0}

        booking_lines = self.env['appointment.booking.line'].sudo()
        # Check Later: Do _read_group with aggregate?
        if users_to_bookings is None:
            booking_lines = self.env['appointment.booking.line'].sudo().search([
                ('appointment_user_id', 'in', all_users.ids),
                ('appointment_type_id.schedule_based_on', '=', 'users'),
                ('event_start', '<', slot_stop_utc),
                ('event_stop', '>', slot_start_utc),
            ])
        elif users_to_bookings:
            for user, booking_line_ids in users_to_bookings.items():
                if user in all_users:
                    booking_lines |= booking_line_ids
            booking_lines = booking_lines.filtered(lambda bl: bl.event_start < slot_stop_utc and bl.event_stop > slot_start_utc)

        users_booking_lines = booking_lines.grouped('appointment_user_id')

        users_remaining_capacity = {}
        max_capacity = self.user_capacity if self.manage_capacity else self.max_bookings
        for user in all_users:
            users_remaining_capacity[user] = max_capacity - sum(booking_line.capacity_used for booking_line in users_booking_lines.get(user, []))

        users_remaining_capacity.update(total_remaining_capacity=sum(users_remaining_capacity.values()))
        return users_remaining_capacity

    def _slot_availability_prepare_users_values_bookings(self, users, start_dt_utc, end_dt_utc):
        """ This method computes bookings of users between start_dt and end_dt
        of appointment check. Also, users are not shared between multiple appointment
        type. So we must consider all bookings in order to avoid booking them more than once
        in multiple appointments per slot. (see ``_slot_availability_is_user_available()``)

        :param <res.users> users: prepare values to check availability
          of those users against given appointment boundaries. At this point
          timezone should be correctly set in context of those users;
        :param datetime start_dt_utc: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt_utc: end of appointment check boundary. Timezoned to UTC;

        :return: dict containing main values for computation, formatted like
          {
            'users_to_bookings': bookings, formatted as a dict
              {
                'appointment_user_id': recordset of booking line,
                ...
              },
          }
        """

        users_to_bookings = {}
        if users:
            booking_lines = self.env['appointment.booking.line'].sudo().search([
                ('appointment_user_id', 'in', users.ids),
                ('appointment_type_id.schedule_based_on', '=', 'users'),
                ('event_stop', '>', datetime.combine(start_dt_utc, time.min)),
                ('event_start', '<', datetime.combine(end_dt_utc, time.max)),
            ])

            users_to_bookings = booking_lines.grouped('appointment_user_id')
        return {
            'users_to_bookings': users_to_bookings,
        }

    def _slot_availability_prepare_users_values(self, staff_users, start_dt, end_dt):
        """ Hook method used to prepare useful values in the computation of slots
        availability. Purpose is to prepare values (event meetings notably)
        in batch instead of doing it in a loop in ``_slots_fill_users_availability``.

        Can be overridden to add custom values preparation to be used in custom
        overrides of ``_slot_availability_is_user_available()``.

        :param <res.users> staff_users: prepare values to check availability
          of those users against given appointment boundaries. At this point
          timezone should be correctly set in context of those users;
        :param datetime start_dt: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt: end of appointment check boundary. Timezoned to UTC;

        :return: dict containing main values for computation, formatted like
          {
            'partner_to_events': meetings (not declined), based on user_partner_id
              (see ``_slot_availability_prepare_users_values_meetings()``);
          },
          {
            'users_to_bookings': bookings based on users
              (see ``_slot_availability_prepare_users_values_bookings()``);
          }
        """

        users_values = self._slot_availability_prepare_users_values_meetings(staff_users, start_dt, end_dt)
        users_values.update(self._slot_availability_prepare_users_values_bookings(staff_users, start_dt, end_dt))
        return users_values

    def _slot_availability_prepare_users_values_meetings(self, staff_users, start_dt, end_dt):
        """ This method computes meetings of users between start_dt and end_dt
        of appointment check.

        :param <res.users> staff_users: prepare values to check availability
          of those users against given appointment boundaries. At this point
          timezone should be correctly set in context of those users;
        :param datetime start_dt: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt: end of appointment check boundary. Timezoned to UTC;

        :return: dict containing main values for computation, formatted like
          {
            'partner_to_events': meetings (not declined), formatted as a dict
              {
                'user_partner_id': dict of day-based meetings: {
                  'date in UTC': calendar events;
                  'date in UTC': calendar events;
                  ...
              },
              { ... }
            }
        """
        related_partners = staff_users.partner_id

        # perform a search based on start / end being set to day min / day max
        # in order to include day-long events without having to include conditions
        # on start_date and allday
        all_events = self.env['calendar.event']
        if related_partners:
            domain = Domain([
                ('partner_ids', 'in', related_partners.ids),
                ('show_as', '=', 'busy'),
                ('stop', '>=', datetime.combine(start_dt, time.min)),
                ('start', '<=', datetime.combine(end_dt, time.max)),
            ])
            # todo: clean in master: method arguments?
            ignore_event_ids = self.env.context.get('ignore_event_ids', False)
            if ignore_event_ids:
                domain &= Domain('id', 'not in', ignore_event_ids)
            all_events = self.env['calendar.event'].search(domain, order='start asc')
        partner_to_events = {}
        for event in all_events:
            for attendee in event.attendee_ids.filtered_domain([
                ('state', '!=', 'declined'),
                ('partner_id', 'in', related_partners.ids)
            ]):
                for day_dt in rrule.rrule(freq=rrule.DAILY,
                                          dtstart=event.start.date(),
                                          until=event.stop.date(),
                                          interval=1):
                    partner_events = partner_to_events.setdefault(attendee.partner_id, {})
                    date_date = day_dt.date()  # map per day, not per hour
                    if partner_events.get(date_date):
                        partner_events[date_date] += event
                    else:
                        partner_events[date_date] = event

        return {'partner_to_events': partner_to_events}

    # --------------------------------------
    # Resources - Slots Availability
    # --------------------------------------

    def _slots_fill_resources_availability(self, slots, start_dt_utc, end_dt_utc, filter_resources=None, asked_capacity=1):
        """ Fills the slot structure with a list of available resources

        :param list slots: slots (list of slot dict), as generated by ``_slots_generate``;
        :param datetime start_dt_utc: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt_utc: end of appointment check boundary. Timezoned to UTC;
        :param <appointment.resource> filter_resources: filter available slots for those resources (can be a singleton
          for fixed appointment types or can contain several resources)
          If not set, use all resources assigned to this appointment type.
        :param integer asked_capacity: asked capacity for the appointment

        :return: None but instead update ``slots`` adding ``available_resource_ids``
            "available_resource_ids" containing the resources ids which are available for the slot
        """
        if self.resource_total_capacity < asked_capacity:
            return False
        available_resources = [
            resource.with_context(tz=resource.tz)
            for resource in (filter_resources or self.resource_ids)
        ]
        available_resources = self.env['appointment.resource'].concat(*available_resources)
        available_resources = available_resources.with_prefetch(available_resources.linked_resource_ids.ids)

        availability_values = self._slot_availability_prepare_resources_values(
            available_resources, start_dt_utc, end_dt_utc
        )

        capacity_info_to_best_resources = {}
        for slot in slots:
            capacity_info = {}
            for resource in available_resources:
                if not self._slot_availability_is_resource_available(slot, resource, availability_values):
                    continue
                resources_remaining_capacity = self._get_resources_remaining_capacity(
                    resource,
                    slot['UTC'][0],
                    slot['UTC'][1],
                    resource_to_bookings=availability_values.get('resource_to_bookings'),
                    filter_resources=slot['slot'].restrict_to_resource_ids & available_resources or available_resources,
                    with_linked_resources=self.manage_capacity,
                )
                if resources_remaining_capacity['total_remaining_capacity'] < asked_capacity:
                    continue
                capacity_info[resource] = {
                    'total_remaining_capacity': resources_remaining_capacity['total_remaining_capacity'],
                    'remaining_capacity': resources_remaining_capacity[resource],
                }
                # Keep only the potential linked resources and add them in capacity_info
                del resources_remaining_capacity['total_remaining_capacity']
                del resources_remaining_capacity[resource]
                for linked_resource, remaining_capacity in resources_remaining_capacity.items():
                    if not remaining_capacity or linked_resource in capacity_info:
                        continue
                    capacity_info[linked_resource] = {
                        'total_remaining_capacity': remaining_capacity,
                        'remaining_capacity': remaining_capacity,
                    }
            capacity_info = frozendict(capacity_info)
            if capacity_info:
                # Compute the best resource a single time for each capacity info
                if not capacity_info_to_best_resources.get(capacity_info):
                    best_resources_selected = self._slot_availability_select_best_resources(
                        capacity_info,
                        asked_capacity,
                    )
                    capacity_info_to_best_resources[capacity_info] = best_resources_selected
                else:
                    best_resources_selected = capacity_info_to_best_resources[capacity_info]
                if best_resources_selected:
                    slot['available_resource_ids'] = best_resources_selected

    def _slot_availability_is_resource_available(self, slot, resource, availability_values):
        """ This method verifies if the resource is available on the given slot.
        It checks whether the resource has bookings clashing and if it
        is included in slot's restricted resources.

        Can be overridden to add custom checks.

        :param dict slot: a slot as generated by ``_slots_generate``;
        :param <appointment.resource> resource: resource to check against slot boundaries.
          At this point timezone should be correctly set in context;
        :param dict availability_values: dict of data used for availability check.
          See ``_slot_availability_prepare_resources_values()`` for more details;

        :return: boolean: is resource available for an appointment for given slot
        """
        if slot['slot'].restrict_to_resource_ids and resource not in slot['slot'].restrict_to_resource_ids:
            return False

        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
        resource_to_bookings = availability_values.get('resource_to_bookings')
        # Check if there is already a booking line for the time slot and make it unavailable
        # if manage capacity is on and resource is not shareable.
        # This avoid to mark the resource as "available" and compute unnecessary remaining capacity computation
        # because of potential linked resources.
        if resource_to_bookings.get(resource):
            if resource_to_bookings[resource].filtered(lambda bl: bl.event_start < slot_end_dt_utc and bl.event_stop > slot_start_dt_utc):
                return resource.shareable if self.manage_capacity else True

        slot_start_dt_utc_l, slot_end_dt_utc_l = pytz.utc.localize(slot_start_dt_utc), pytz.utc.localize(slot_end_dt_utc)
        for i_start, i_stop in availability_values.get('resource_unavailabilities', {}).get(resource, []):
            if i_start != i_stop and i_start < slot_end_dt_utc_l and i_stop > slot_start_dt_utc_l:
                return False

        return True

    def _get_resources_remaining_capacity(self, resources, slot_start_utc, slot_stop_utc, resource_to_bookings=None, with_linked_resources=True, filter_resources=None):
        """ Compute the remaining capacities for resources in a particular time slot.
            :param <appointment.resource> resources : record containing one or a multiple of resources
            :param datetime slot_start_utc: start of slot (in naive UTC)
            :param datetime slot_stop_utc: end of slot (in naive UTC)
            :param list resource_to_bookings: list of resource linked to their booking lines from the prepared value.
                If no value is passed, then we search manually the booking lines (used for the appointment validation step)
            :param bool with_linked_resources: If true we take into account the linked resources for the computation.
                The fact to not take into account the linked resources could be useful when checking the remaining capacity
                of particular resources (e.g. when we check if the resources are still available when a customer book an
                appointment or to compute remaining capacity for a particular resource)
            :param <appointment.resource> filter_resources: filter the resources impacted with this value
            :returns: remaining_capacity
        """
        self.ensure_one()

        all_resources = ((resources | resources.linked_resource_ids) if with_linked_resources else resources) & self.resource_ids
        if filter_resources:
            all_resources &= filter_resources
        if not resources:
            return {'total_remaining_capacity': 0}

        booking_lines = self.env['appointment.booking.line'].sudo()
        if resource_to_bookings is None:
            booking_lines = self.env['appointment.booking.line'].sudo().search([
                ('appointment_resource_id', 'in', all_resources.ids),
                ('event_start', '<', slot_stop_utc),
                ('event_stop', '>', slot_start_utc),
            ])
        elif resource_to_bookings:
            for resource, booking_line_ids in resource_to_bookings.items():
                if resource in all_resources:
                    booking_lines |= booking_line_ids
            booking_lines = booking_lines.filtered(lambda bl: bl.event_start < slot_stop_utc and bl.event_stop > slot_start_utc)

        resources_booking_lines = booking_lines.grouped('appointment_resource_id')
        resources_remaining_capacity = {
            resource: (resource.capacity if self.manage_capacity else self.max_bookings) - sum(booking_line.capacity_used for booking_line in resources_booking_lines.get(resource, []))
            for resource in all_resources
        }
        resources_remaining_capacity.update(total_remaining_capacity=sum(resources_remaining_capacity.values()))
        return resources_remaining_capacity

    def _slot_availability_select_best_resources(self, capacity_info, asked_capacity):
        """ Check and select the best resources for the capacity needed
            :params main_resources_remaining_capacity <dict>: dict containing remaining capacities of resources available
            :params linked_resources_remaining_capacity <dict>: dict containing remaining capacities of linked resources
            :params asked_capacity <integer>: asked capacity for the appointment
            :returns: we return recordset of best resources selected
        """
        self.ensure_one()
        available_resources = self.env['appointment.resource'].concat(*capacity_info.keys()).sorted('sequence')
        if not available_resources:
            return self.env['appointment.resource']
        if not self.manage_capacity:
            return available_resources[0] if not (self.is_date_first and not self.is_auto_assign) else available_resources

        perfect_matches = available_resources.filtered(
            lambda resource: resource.capacity == asked_capacity and capacity_info[resource]['remaining_capacity'] == asked_capacity)
        if perfect_matches:
            return available_resources if self.is_date_first and not self.is_auto_assign else perfect_matches[0]

        first_resource_selected = available_resources[0]
        first_resource_selected_capacity_info = capacity_info.get(first_resource_selected)
        first_resource_selected_capacity = first_resource_selected_capacity_info['remaining_capacity']
        capacity_needed = asked_capacity - first_resource_selected_capacity
        if capacity_needed > 0:
            # Get the best resources combination based on the capacity we need and the resources available.
            resource_possible_combinations = available_resources._get_filtered_possible_capacity_combinations(
                asked_capacity,
                capacity_info,
            )
            if not resource_possible_combinations:
                return self.env['appointment.resource']
            if asked_capacity <= first_resource_selected_capacity_info['total_remaining_capacity'] - first_resource_selected_capacity:
                r_ids = first_resource_selected.ids + first_resource_selected.linked_resource_ids.ids
                resource_possible_combinations = list(filter(lambda cap: any(r_id in r_ids for r_id in cap[0]), resource_possible_combinations))
            resources_combinations_exact_capacity = list(filter(lambda cap: cap[1] == asked_capacity, resource_possible_combinations))
            resources_combination_selected = resources_combinations_exact_capacity[0] if resources_combinations_exact_capacity else resource_possible_combinations[0]
            return available_resources.filtered(lambda resource: resource.id in resources_combination_selected[0])

        if self.is_date_first and not self.is_auto_assign:
            return available_resources

        return first_resource_selected

    def _slot_availability_prepare_resources_values(self, resources, start_dt_utc, end_dt_utc):
        """ The purpose is the same as ``_slot_availability_prepare_users_values``
        Instead of meetings, here we get booking lines for each resources.


        :param <appointment.resource> resources: prepare values to check availability
          of those resources against given appointment boundaries. At this point
          timezone should be correctly set in context of those resources;
        :param datetime start_dt_utc: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt_utc: end of appointment check boundary. Timezoned to UTC;

        :return: dict containing main values for computation, formatted like
          {
            'resource_to_bookings': bookings based on resources
              (see ``_slot_availability_prepare_resources_bookings_values()``);
          }
        """
        resources_values = self._slot_availability_prepare_resources_bookings_values(resources, start_dt_utc, end_dt_utc)
        resources_values.update(self._slot_availability_prepare_resources_leave_values(resources, start_dt_utc, end_dt_utc))
        return resources_values

    def _slot_availability_prepare_resources_bookings_values(self, resources, start_dt_utc, end_dt_utc):
        """ This method computes bookings of resources between start_dt and end_dt
        of appointment check. Also, resources can be shared between multiple appointment
        type. So we must consider all bookings in order to avoid booking them more than once.

        :param <appointment.resource> resources: prepare values to check availability
          of those resources against given appointment boundaries. At this point
          timezone should be correctly set in context of those resources;
        :param datetime start_dt_utc: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt_utc: end of appointment check boundary. Timezoned to UTC;

        :return: dict containing main values for computation, formatted like
          {
            'resource_to_bookings': bookings, formatted as a dict
              {
                'appointment_resource_id': recordset of booking line,
                ...
              },
          }
        """

        resource_to_bookings = {}
        if resources:
            domain = Domain([
                ('appointment_resource_id', 'in', resources.ids),
                ('event_stop', '>', datetime.combine(start_dt_utc, time.min)),
                ('event_start', '<', datetime.combine(end_dt_utc, time.max)),
            ])
            # todo: clean in master: method arguments?
            ignore_event_ids = self.env.context.get('ignore_event_ids', False)
            if ignore_event_ids:
                domain &= Domain('calendar_event_id', 'not in', ignore_event_ids)
            booking_lines = self.env['appointment.booking.line'].sudo().search(domain)
            resource_to_bookings = booking_lines.grouped('appointment_resource_id')

        return {
            'resource_to_bookings': resource_to_bookings,
        }

    def _slot_availability_prepare_resources_leave_values(self, appointment_resources, start_dt_utc, end_dt_utc):
        """Retrieve a list of unavailabilities for each resource.

        :param <appointment.resource> appointment_resources: resources to get unavalabilities for;
        :param datetime start_dt_utc: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt_utc: end of appointment check boundary. Timezoned to UTC;
        :return: dict mapping resource ids to ordered list of unavailable datetime intervals
           {
             resource_unavailabilities: {
               <appointment.resource, 1>: [
                   [datetime(2022, 07, 07, 12, 0, 0), datetime(2022, 07, 07, 13, 0, 0)],
                   [datetime(2022, 07, 07, 16, 0, 0), datetime(2022, 07, 08, 06, 0, 0)],
                   ...],
               ...
             }
           }
        """
        unavailabilities = appointment_resources.sudo().resource_id._get_unavailable_intervals(start_dt_utc, end_dt_utc)
        return {'resource_unavailabilities': {
            resource: unavailabilities.get(resource.sudo().resource_id.id, []) for resource in appointment_resources
        }}
