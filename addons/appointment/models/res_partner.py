# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import pytz
from datetime import datetime, time

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    upcoming_appointment_ids = fields.Many2many('calendar.event', string="Upcoming Appointments", compute="_compute_upcoming_appointment_ids")

    def _compute_upcoming_appointment_ids(self):
        partner_upcoming_appointments = dict(self.env['calendar.event']._read_group(
            [('appointment_booker_id', 'in', self.ids), ('appointment_type_id', '!=', False), ('start', '>', datetime.now())],
            ['appointment_booker_id'],
            ['id:recordset'],
        ))
        for partner in self:
            partner.upcoming_appointment_ids = partner_upcoming_appointments.get(partner, False)

    def calendar_verify_availability(self, date_start, date_end, appointment_type=None):
        """ Verify availability of the partner(s) for the appointment between 2 datetimes on their
        calendar. We only verify events that are not linked to an appointment type with resources since
        someone could take multiple appointment for multiple resources. The availability of
        resources is managed separately by booking lines (see ``appointment.booking.line`` model)

        :param datetime date_start: beginning of slot boundary. Not timezoned UTC;
        :param datetime date_end: end of slot boundary. Not timezoned UTC;
        """
        all_events = self.env['calendar.event'].search(
            ['&',
             ('partner_ids', 'in', self.ids),
             '&', '&',
             ('show_as', '=', 'busy'),
             ('stop', '>', datetime.combine(date_start, time.min)),
             ('start', '<', datetime.combine(date_end, time.max)),
            ],
            order='start asc',
        )
        events_excluding_appointment_resource = all_events.filtered(lambda ev: ev.appointment_type_id.schedule_based_on != 'resources')
        for event in events_excluding_appointment_resource:
            if event.allday or (event.start < date_end and event.stop > date_start):
                # Skip marking the staff user unavailable for the same appointment
                if (appointment_type and self <= appointment_type.staff_user_ids.partner_id and
                    event.appointment_type_id == appointment_type):
                    continue
            tz = pytz.timezone(event.user_id.tz) if event.user_id.tz else pytz.utc
            if event.allday:
                start_utc = tz.localize(event.start).astimezone(pytz.utc).replace(tzinfo=None)
                stop_utc = tz.localize(event.stop).astimezone(pytz.utc).replace(tzinfo=None)
            else:
                start_utc = event.start
                stop_utc = event.stop
            if start_utc < date_end and stop_utc > date_start:
                if event.attendee_ids.filtered_domain(
                        [('state', '!=', 'declined'),
                         ('partner_id', 'in', self.ids)]
                    ):
                    return False

        return True
