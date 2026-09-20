# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.appointment.controllers.calendar_view import AppointmentCalendarView
from odoo.fields import Domain
from odoo.http import request


class AppointmentCrmCalendarView(AppointmentCalendarView):

    @classmethod
    def _get_staff_user_appointment_invite_domain(cls, appointment_type, user):
        domain = super()._get_staff_user_appointment_invite_domain(appointment_type, user)
        if 'default_opportunity_id' in request.env.context:
            domain = Domain.AND([domain, [('opportunity_id', '=', request.env.context['default_opportunity_id'])]])
        return domain
