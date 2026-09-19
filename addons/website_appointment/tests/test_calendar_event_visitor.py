from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.addons.website.tests.test_website_visitor import WebsiteVisitorTestsCommon
from odoo.tests.common import tagged


@tagged('website_visitor')
class TestCalendarEventVisitor(AppointmentCommon, WebsiteVisitorTestsCommon):

    def test_compute_email_phone(self):
        """ Check that the email and mobile of the visitor are computed from the
        appointment_booker_id of the calendar event to which the visitor is linked. """
        visitor = self.env['website.visitor'].create({
            'access_token': 'f9d2c6f3b024320ac31248595ac7fcb7',
        })
        # Check that the visitor does not have email and mobile.
        self.assertFalse(visitor.email or visitor.mobile)

        partner_0, partner_1 = self.env['res.partner'].create([{
            'name': 'Test Customer 0',
            'email': '"Test Customer 0" <calendar_event_0@test.example.com>',
            'phone': '+32456001120',
        }, {
            'name': 'Test Customer 1',
            'email': '"Test Customer 1" <calendar_event_1@test.example.com>',
            'phone': '+32456001121',
        }])

        self.env["calendar.event"].create([{
            'name': 'Test event 0',
            'appointment_booker_id': partner_0.id,
            'visitor_id': visitor.id,
        }, {
            'name': 'Test event 1',
            'appointment_booker_id': partner_1.id,
            'visitor_id': visitor.id,
        }])

        # Check that the visitor's email and mobile have been computed from appointment_booker_id
        # of the last event to which the visitor is linked.
        self.assertEqual(visitor.email, '"Test Customer 1" <calendar_event_1@test.example.com>')
        self.assertEqual(visitor.mobile, '+32456001121')

    def test_link_to_visitor_calendar_event(self):
        """ Same as parent's 'test_link_to_visitor' except we also test that
        calendar events are merged into main visitor. """
        main_visitor, linked_visitor = self.env['website.visitor'].create([
            self._prepare_main_visitor_data(),
            self._prepare_linked_visitor_data()
        ])
        all_calendar_events = (main_visitor + linked_visitor).calendar_event_ids
        linked_visitor._merge_visitor(main_visitor)

        # Calendar events of both visitors should be merged into main one.
        self.assertEqual(len(main_visitor.calendar_event_ids), 2)
        self.assertEqual(main_visitor.calendar_event_ids, all_calendar_events)

        self.assertVisitorDeactivated(linked_visitor, main_visitor)

    def _prepare_main_visitor_data(self):
        values = super()._prepare_main_visitor_data()
        values.update({
            'calendar_event_ids': [(0, 0, {
                'name': 'Mitchel Main Calendar Event'
            })]
        })
        return values

    def _prepare_linked_visitor_data(self):
        values = super()._prepare_linked_visitor_data()
        values.update({
            'calendar_event_ids': [(0, 0, {
                'name': 'Mitchel Secondary Calendar Event'
            })]
        })
        return values
