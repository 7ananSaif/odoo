from odoo import api, models, _


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    @api.model
    def get_appointment_type_templates_data(self):
        return super().get_appointment_type_templates_data() | {
            'paid_consultation': {
                'description': _("Let customers book a paid slot in your calendar with you"),
                'icon': '/appointment_account_payment/static/src/img/rfq.svg',
                'template_key': 'paid_consultation',
                'title': _("Paid Consultation"),
            },
            'paid_seats': {
                'description': _("Let customers book a fee per person for activities such as a theater, etc."),
                'icon': '/appointment_account_payment/static/src/img/chair.svg',
                'template_key': 'paid_seats',
                'title': _("Paid Seats"),
            },
        }

    @api.model
    def _get_appointment_type_template_values(self, template_key):
        if template_key == 'paid_consultation':
            return self._prepare_paid_consultation_template_values()
        elif template_key == 'paid_seats':
            return self._prepare_paid_seats_template_values()
        return super()._get_appointment_type_template_values(template_key)

    @api.model
    def _prepare_paid_consultation_template_values(self):
        return {
            'allow_guests': True,
            'appointment_duration': 0.5,
            'slot_creation_interval': 0.5,
            'is_auto_assign': True,
            'show_avatars': False,
            'event_videocall_source': False,
            'has_payment_step': True,
            'location_id': self.env.company.partner_id.id,
            'name': _('Paid Consultation'),
            'product_id': self.env.ref('appointment_account_payment.default_booking_product').id,
        }

    @api.model
    def _prepare_paid_seats_template_values(self):
        return {
            'appointment_duration': 1.0,
            'is_auto_assign': False,
            'is_date_first': True,
            'event_videocall_source': False,
            'has_payment_step': True,
            'location_id': self.env.company.partner_id.id,
            'max_schedule_days': 30,
            'name': _('Paid Seats'),
            'product_id': self.env.ref('appointment_account_payment.default_booking_product').id,
            'resource_ids': [
                (0, 0, {
                    'name': _('Room %s', number),
                    'capacity': capacity,
                }) for number, capacity in enumerate([5, 10, 15, 20], start=1)
            ],
            'manage_capacity': True,
            'schedule_based_on': 'resources',
            'staff_user_ids': [],
        }
