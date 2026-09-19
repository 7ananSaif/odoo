from odoo.addons.appointment.controllers.appointment import AppointmentController
from odoo.http import request


class AppointmentCrmController(AppointmentController):

    def _get_forced_staff_user(self, appointment_type, possible_staff_users):
        """ Fetch the staff user from the leads linked to the visitor's partner if the appointment_type
        has a random staff user selection. """
        forced_user = super()._get_forced_staff_user(appointment_type, possible_staff_users)
        if forced_user or not appointment_type.lead_create or not appointment_type.is_auto_assign:
            return forced_user

        if partner := self._get_customer_partner():
            return request.env['crm.lead'].sudo().search(
                [('user_id', 'in', possible_staff_users.ids), ('partner_id', '=', partner.id)],
                order='id DESC',
                limit=1
            ).user_id
        return self.env['res.users']
