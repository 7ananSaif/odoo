# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta

from odoo.tests import users
from odoo.tools import html2plaintext
from odoo.addons.appointment_crm.tests.common import TestAppointmentCrmCommon
from odoo.addons.base.tests.common import HttpCaseWithUserPortal
from odoo.tests import common


class AppointmentCRMTest(TestAppointmentCrmCommon):

    @users('user_employee')
    def test_create_opportunity(self):
        """ Test the creation of a lead based on the creation of an event
        with appointment type configured to create lead
        """
        # add current user to staff users so they can read the appointment during create
        self.appointment_type_create.sudo().staff_user_ids += self.env.user
        event = self._create_meetings_from_appointment_type(
            self.appointment_type_create, self.user_sales_leads, self.contact_1
        )

        self.assertEqual(event.res_model_id, self.env['ir.model']._get('crm.lead'),
            "Event should be linked with the model crm.lead")
        self.assertTrue(event.res_id)
        self.assertTrue(event.opportunity_id)
        lead = event.opportunity_id.sudo()
        self.assertEqual(lead.user_id, event.user_id)
        self.assertEqual(lead.name, event.name)
        self.assertTrue(lead.description)
        self.assertIn('crm_leads@test.example.com', lead.description, 'Description should contain contact info of the attendee')
        self.assertEqual(html2plaintext(lead.description), html2plaintext(event.description))
        self.assertEqual(lead.partner_id, self.contact_1)
        self.assertTrue(lead.activity_ids[0], "Lead should have a next activity")
        self.assertNotIn(self.env.user.partner_id, lead.message_partner_ids)

        next_activity = lead.activity_ids[0]
        self.assertEqual(next_activity.date_deadline, event.start_date)
        self.assertEqual(next_activity.calendar_event_id, event)

    @users('user_employee')
    def test_create_opportunity_multi(self):
        """ Test the creation of a lead based on the creation of an event
        with appointment type configured to create lead
        """
        # add current user to staff users so they can read the appointment during create
        (self.appointment_type_create + self.appointment_type_nocreate).sudo().staff_user_ids += self.env.user
        events = self.env['calendar.event'].create([
            self._prepare_event_value(
                self.appointment_type_create,
                self.user_sales_leads,
                self.contact_1,
            ),
            self._prepare_event_value(
                self.appointment_type_nocreate,
                self.user_sales_leads,
                self.contact_2,
            ),
            self._prepare_event_value(
                self.appointment_type_create,
                self.user_sales_leads,
                self.contact_1,
                start=datetime.now() + timedelta(hours=1),
                start_date=datetime.now() + timedelta(hours=1),
                stop=datetime.now() + timedelta(hours=2),
        )]).sudo()
        self.assertTrue(events[0].opportunity_id)
        self.assertFalse(events[1].opportunity_id)
        self.assertTrue(events[2].opportunity_id)
        event1 = events[0]
        next_activity1 = event1.opportunity_id.activity_ids[0]
        self.assertEqual(next_activity1.date_deadline, event1.start_date)
        event2 = events[2]
        next_activity2 = event2.opportunity_id.activity_ids[0]
        self.assertEqual(next_activity2.date_deadline, event2.start_date)

    @users('user_employee')
    def test_create_opportunity_multi_company(self):
        """ Test the creation of a lead when the assignee of the event is in a
        different company than the event creator
        """
        self._activate_multi_company()
        self.user_employee.write({
            'company_ids': [self.company_2.id],
            'company_id': self.company_2,
        })

        # add current user to staff users so they can read the appointment during create
        self.appointment_type_create.sudo().staff_user_ids += self.env.user
        event = self.env['calendar.event'].create(self._prepare_event_value(
            self.appointment_type_create,
            self.user_sales_leads,
            self.contact_1,
        ))

        # Sanity checks
        # event organizer -> company_main, event creator -> company_2
        self.assertEqual(event.user_id.company_id, self.company_main)
        self.assertEqual(self.user_employee.company_id, self.company_2)

        # Check if lead is created in company_main
        self.assertTrue(event.opportunity_id)
        lead = event.opportunity_id
        self.assertEqual(lead.user_id, event.user_id)
        self.assertEqual(lead.company_id, self.company_main)

    def test_no_create_lead(self):
        """ Make sure no lead is created for appointment type with create_lead=False """
        event = self._create_meetings_from_appointment_type(
            self.appointment_type_nocreate, self.user_sales_leads, self.contact_1
        )
        self.assertFalse(event.opportunity_id)

    def test_no_partner(self):
        """ Make sure no lead is created if there is no external partner attempting the appointment """
        event = self._create_meetings_from_appointment_type(
            self.appointment_type_create, self.user_sales_leads, self.user_sales_leads.partner_id
        )
        self.assertFalse(event.opportunity_id)

    def test_two_partner(self):
        """ Make sure lead is created if there is two external partner attempting the appointment """
        event_values = self._prepare_event_value(
            self.appointment_type_create,
            self.user_sales_leads,
            self.contact_1,
        )
        event_values['partner_ids'].append((4, self.contact_2.id, False))
        event = self.env['calendar.event'].create(event_values)
        self.assertTrue(event.opportunity_id)

    def test_no_type(self):
        """ Make sure no lead is created, if the appointment type is empty """
        event = self._create_meetings_from_appointment_type(
            self.env['appointment.type'], self.user_sales_leads, self.contact_1
        )
        self.assertFalse(event.opportunity_id)


@common.tagged('post_install', '-at_install')
class AppointmentCRMHttpTest(TestAppointmentCrmCommon, HttpCaseWithUserPortal):

    @users("portal")
    def test_appointment_forced_staff_user_tour(self):
        """ Check that the lead of the last appointment is used to force the staff
        user of the next appointment and that it is linked to this one when it is
        created. """
        self.start_tour('/appointment', 'appointment_crm_forced_staff_user_tour', login='portal')

        created_lead = self.env['crm.lead'].sudo().search([
            ('partner_id', '=', self.env.user.partner_id.id),
            ('user_id', '=', self.user_sales_leads.id)
        ])
        # Check the reuse of the lead of the first appointment by the second one.
        self.assertEqual(len(created_lead), 1)
        self.assertEqual(len(created_lead.calendar_event_ids), 2)

        # Check the reassignment of the staff user to each event.
        self.assertTrue(all(staff_user == self.user_sales_leads for staff_user in created_lead.calendar_event_ids.user_id))
