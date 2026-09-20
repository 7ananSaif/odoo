# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    def _prepare_calendar_event_values(
        self, asked_capacity, booking_line_values, description, duration, allday,
        appointment_invite, guests, name, customer, staff_user, start, stop
    ):
        values = super()._prepare_calendar_event_values(
            asked_capacity, booking_line_values, description, duration, allday,
            appointment_invite, guests, name, customer, staff_user, start, stop
        )

        if not values.get('phone_number') and customer.phone:
            values['phone_number'] = customer.phone

        return values
