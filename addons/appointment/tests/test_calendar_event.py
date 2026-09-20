from odoo import exceptions
from odoo.tests import users
from .common import AppointmentCommon


class AppointmentCalendarEventTest(AppointmentCommon):
    @users('apt_manager')
    def test_appointment_calendar_event_inverse_capacity(self):
        """Ensure the inverse appropriately assigns bookings such that the input reserved capacity is preserved.

        If the resources cannot hold the requested capacity, an error should be raised.
        In the case of appointments where capacity is not managed, the capacity should be 1 per resource selected
        regardless of their capacity.
        """
        user_appointment = self.apt_type_manage_capacity_users
        user_appointment.staff_user_ids += self.env.user

        resource_appointment = self.apt_type_resource
        resource_appointment.resource_ids = [
            (0, 0, {'name': '1', 'capacity': 1}),
            (0, 0, {'name': '3', 'capacity': 3}),
            (0, 0, {'name': '5', 'capacity': 5}),
        ]
        base_dict = {'manage_capacity': False, 'user_capacity': 1}

        test_cases = [
            (user_appointment, {'manage_capacity': False, 'user_capacity': 5}, {}, 5, 1),
            (user_appointment, {'manage_capacity': True, 'user_capacity': 5}, {}, 4, 4),
            (user_appointment, {'manage_capacity': True, 'user_capacity': 5}, {}, 5, 5),
            (user_appointment, {'manage_capacity': True, 'user_capacity': 5}, {}, 6, None),
            (resource_appointment, {'manage_capacity': False}, {'resource_ids': resource_appointment.resource_ids}, 2, 3),
            (resource_appointment, {'manage_capacity': False}, {'resource_ids': resource_appointment.resource_ids}, 5, 3),
            (resource_appointment, {'manage_capacity': True}, {'resource_ids': resource_appointment.resource_ids}, 8, 8),
            (resource_appointment, {'manage_capacity': True}, {'resource_ids': resource_appointment.resource_ids}, 10, None),
        ]

        for appointment_type, appointment_vals, event_vals, total_capacity_reserved, expected_total_capacity_reserved in test_cases:
            with self.subTest(
                appointment=appointment_type.name, appointment_vals=appointment_vals, event_vals=event_vals,
                total_capacity_reserved=total_capacity_reserved, expected_total_capacity_reserved=expected_total_capacity_reserved,
            ):
                appointment_type.write(base_dict | appointment_vals)
                calendar_event_vals = {
                    'appointment_type_id': appointment_type.id,
                    'name': 'Test Booking',
                    'total_capacity_reserved': total_capacity_reserved,
                } | event_vals
                if expected_total_capacity_reserved is None:
                    with self.assertRaises(exceptions.UserError):
                        self.env['calendar.event'].create(calendar_event_vals)
                else:
                    event = self.env['calendar.event'].create(calendar_event_vals)
                    event.invalidate_recordset(['total_capacity_reserved', 'user_id', 'resource_ids'])
                    self.assertEqual(event.total_capacity_reserved, expected_total_capacity_reserved)
                    event.unlink()
