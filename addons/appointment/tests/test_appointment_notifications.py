# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from freezegun import freeze_time

from odoo import Command, http
from odoo.tests import Form, tagged, users
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from odoo.addons.mail.tests.common import MailCase
from odoo.addons.appointment.tests.common import AppointmentCommon


@tagged('mail_flow')
class AppointmentTestTracking(AppointmentCommon, MailCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.apt_type_follower = cls.env['res.partner'].create([{
            'name': 'Apt Type Follower',
            'country_id': cls.env.ref('base.be').id,
            'email': 'follower@test.lan',
            'phone': '+32 81 212 220'
        }])
        cls.apt_type_bxls_2days.message_subscribe(partner_ids=cls.apt_type_follower.ids)

        cls.appointment_attendee_ids = cls.env['res.partner'].create([{
            'name': f'Customer {attendee_indx}',
            'email': f'customer_{attendee_indx}@test.lan'
        } for attendee_indx in range(2)])

        cls.appointment_meeting_id = cls.env['calendar.event'].with_context(cls._test_context).create({
            'name': 'Test Tracking Appointment',
            'partner_ids': [Command.link(p) for p in cls.apt_manager.partner_id.ids + cls.appointment_attendee_ids.ids],
            'start': cls.reference_now,
            'stop': cls.reference_now + timedelta(hours=1),
            'user_id': cls.apt_manager.id,
            'appointment_type_id': cls.apt_type_bxls_2days.id
        }).with_context(mail_notrack=False)

    @freeze_time('2017-01-01')
    @users('apt_manager')
    def test_archive_message(self):
        """Check that we send cancelation notifications when archiving an appointment."""
        meeting = self.appointment_meeting_id
        self.assertGreater(meeting.start, datetime.now(), 'Test expects `datetime.now` to be before start of meeting')
        with self.mock_mail_gateway(), self.mock_mail_app():
            meeting.active = False
            self.flush_tracking()

        self.assertEqual(len(self._new_msgs), 2, 'Expected a tracking message and a cancelation template')
        self.assertTracking(
            self._new_msgs[0],
            [('active', 'boolean', True, False)]
        )
        self.assertEqual(self.ref('appointment.mt_calendar_event_canceled'), self._new_msgs[1].subtype_id.id,
                         'Expected a template cancelation message')

        with self.mock_mail_gateway(), self.mock_mail_app():
            meeting.active = True
            self.flush_tracking()

        self.assertEqual(len(self._new_msgs), 4,
            'Expected a tracking message and confirmation mails')  # 1 track message + 3 mails(1 apt_manager + 2 customers)
        self.assertTracking(
            self._new_msgs[3],
            [('active', 'boolean', False, True)]
        )
        #  Check all mails are sent after confirming the booking
        for attendee in meeting.partner_ids:
            self.assertSentEmail(
                self.apt_manager.partner_id, attendee, subject='Invitation to Test Tracking Appointment'
            )

    @freeze_time('2017-01-01')
    def test_cancel_meeting_message(self):
        """ Make sure appointments send a custom message on archival/cancellation """
        meeting1 = self.appointment_meeting_id
        meeting2 = meeting1.copy()
        self.flush_tracking()
        self.assertGreater(meeting1.start, datetime.now(), 'Test expects `datetime.now` to be before start of meeting')
        self.assertEqual(meeting1.partner_ids, self.apt_manager.partner_id + self.appointment_attendee_ids,
                         'Manager and attendees should be there')
        self.assertEqual(meeting1.message_partner_ids, self.apt_type_follower,
                         'All attendees and concerned users should not be added in followers, keeping only those manually added')

        with self.mock_mail_gateway(), self.mock_mail_app():
            meeting1.with_context(mail_notify_force_send=True).action_cancel_meeting(self.appointment_attendee_ids[0].ids)
            self.flush_tracking()

        self.assertFalse(meeting1.active, 'Meeting should be archived')
        self.assertMessageFields(self._new_msgs[0], {
            'body': f'<p>Appointment cancelled by: {self.appointment_attendee_ids[0].display_name}</p>',
            'notification_ids': self.env['mail.notification'],
            'subtype_id': self.env.ref('mail.mt_note'),
        })

        # check with no partner
        with self.mock_mail_gateway(), self.mock_mail_app():
            meeting2.with_user(self.apt_manager).action_cancel_meeting([])
            self.flush_tracking()
        self.assertFalse(meeting1.active, 'Meeting should be archived')
        self.assertMessageFields(self._new_msgs[0], {
            'body': '<p>Appointment cancelled</p>',
            'notification_ids': self.env['mail.notification'],
            'subtype_id': self.env.ref('mail.mt_note'),
        })

    @freeze_time('2017-01-01')
    def test_request_meeting_message_for_manual_confirmation(self):
        """ Make sure appointments send a custom mail on request to all relevant contacts """
        apt_type = self.apt_type_bxls_2days
        apt_type.auto_confirm = False
        apt_type.schedule_based_on = 'users'
        phone_question = apt_type._get_main_phone_question()
        self.assertTrue(phone_question)
        self._create_invite_test_data()

        self.authenticate(None, None)
        now_str = self.reference_now.strftime(DTF)
        with self.mock_mail_gateway(), self.mock_mail_app():
            apt_data = {
                "allday": 0,
                "asked_capacity": 1,
                "available_resource_ids": None,
                "csrf_token": http.Request.csrf_token(self),
                "datetime_str": now_str,
                "duration_str": "1.0",
                "email": 'someattendee@test.lan',
                "filter_appointment_type_ids": apt_type.ids,  # required for invites
                "invite_token": self.invite_apt_type_bxls_2days.access_token,
                "name": "Test Online Meeting",
                f"question_{phone_question.id}": "12345",
                "staff_user_id": self.staff_user_bxls.id
            }
            response = self.url_open(f"/appointment/{apt_type.id}/submit", data=apt_data)

            self.assertEqual(response.status_code, 200)
            self.flush_tracking()

        calendar_event = self.env['calendar.event'].search([
            ('name', '=', 'Test Online Meeting - Bxls Appt Type Booking')
        ], limit=1)
        self.assertTrue(calendar_event, "Calendar event was not created.")

        attendee = calendar_event.partner_ids - calendar_event.partner_id
        self.assertEqual(attendee.email_normalized, 'someattendee@test.lan')

        # Request mails
        self.assertEqual(len(self._new_mails), 3)
        # find the message and ensure each one has 1 recipient, assertMailMail gets a bit confused here
        booked_follower_mail = self.assertMailMail(
            self.apt_type_follower, 'sent',
            author=self.staff_user_bxls.partner_id,
            email_values={
                'subject': 'Appointment Requested: Bxls Appt Type',
                'email_from': self.staff_user_bxls.email_formatted,
            },
        )
        attendee_mail = self.assertMailMail(
            attendee, 'sent',
            author=self.staff_user_bxls.partner_id,
            email_values={
                'subject': 'Invitation to Test Online Meeting - Bxls Appt Type Booking',
                'email_from': self.staff_user_bxls.email_formatted,
            },
        )
        organizer_mail = self.assertMailMail(
            self.staff_user_bxls.partner_id, 'sent',
            author=self.staff_user_bxls.partner_id,
            email_values={
                'subject': 'Invitation to Test Online Meeting - Bxls Appt Type Booking',
                'email_from': self.staff_user_bxls.email_formatted,
            },
        )
        self.assertEqual(booked_follower_mail | attendee_mail | organizer_mail, self._new_mails)

        with self.mock_mail_gateway(), self.mock_mail_app():
            # Confirm the appointment manually
            with Form(calendar_event.with_user(self.apt_manager)) as form:
                form.appointment_status = 'booked'

        # Confirmation mails
        self.assertEqual(len(self._new_mails), 2)
        attendee_mail = self.assertMailMail(
            attendee, 'sent',
            author=self.staff_user_bxls.partner_id,
            email_values={
                'subject': 'Invitation to Test Online Meeting - Bxls Appt Type Booking',
                'email_from': self.staff_user_bxls.email_formatted,
            },
        )
        organizer_mail = self.assertMailMail(
            self.staff_user_bxls.partner_id, 'sent',
            author=self.staff_user_bxls.partner_id,
            email_values={
                'subject': 'Invitation to Test Online Meeting - Bxls Appt Type Booking',
                'email_from': self.staff_user_bxls.email_formatted,
            },
        )
        self.assertEqual(attendee_mail | organizer_mail, self._new_mails)
