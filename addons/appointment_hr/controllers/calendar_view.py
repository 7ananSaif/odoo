# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.appointment.controllers.calendar_view import AppointmentCalendarView


class AppointmentHRCalendarView(AppointmentCalendarView):

    # Utility Methods
    # ----------------------------------------------------------

    @classmethod
    def _prepare_appointment_type_anytime_values(cls, user):
        appt_type_vals = super()._prepare_appointment_type_anytime_values(user)
        appt_type_vals.update(work_hours_activated=True)
        return appt_type_vals
