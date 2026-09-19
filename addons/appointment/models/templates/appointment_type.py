from odoo import api, models, _


class AppointmentType(models.Model):
    '''
    This file inherits the appointment.type model and centralize all methods linked
    to appointment type templates in a separate file. These templates are used to
    ease the onboarding and load specific configurations, hinted by their description.
    They appear instead of the helper on appointment.type list and kanban views when
    no appointment exists.
    '''
    _inherit = 'appointment.type'

    @api.model
    def action_setup_appointment_type_template(self, template_key):
        action = self.env['ir.actions.act_window']._for_xml_id('appointment.appointment_type_action')
        template_values = self._get_appointment_type_template_values(template_key)
        action['res_id'] = self.env['appointment.type'].create(template_values).id
        action['views'] = [[self.env.ref('appointment.appointment_type_view_form').id, 'form']]
        return action

    @api.model
    def get_appointment_type_templates_data(self):
        '''
        Returns onboarding template names and all linked necessary rendering information.
        '''
        return {
            'meeting': {
                'description': _("Let others book a meeting in your calendar"),
                'icon': '/appointment/static/src/img/guy.svg',
                'template_key': 'meeting',
                'title': _("Meeting"),
            },
            'video_call': {
                'description': _("Schedule a video meeting in a virtual room with one or more participants"),
                'icon': '/appointment/static/src/img/headset.svg',
                'template_key': 'video_call',
                'title': _("Video Call"),
            },
            'table_booking': {
                'description': _("Let customers book a table in your restaurant or bar"),
                'icon': '/appointment/static/src/img/foods.svg',
                'template_key': 'table_booking',
                'title': _("Table Booking"),
            },
            'book_resource': {
                'description': _("Let customers book a resource such as a room, a tennis court, etc."),
                'icon': '/appointment/static/src/img/clock.svg',
                'template_key': 'book_resource',
                'title': _("Book a Resource"),
            },
        }

    def _get_appointment_type_template_values(self, template_key):
        if template_key == 'meeting':
            return self._prepare_meeting_template_values()
        elif template_key == 'video_call':
            return self._prepare_video_call_template_values()
        elif template_key == 'table_booking':
            return self._prepare_table_booking_template_values()
        elif template_key == 'book_resource':
            return self._prepare_book_resource_template_values()
        return {}

    @api.model
    def _prepare_meeting_template_values(self):
        return {
            'name': _('Meeting'),
            'appointment_duration': 1.0,
            'is_auto_assign': False,
            'is_date_first': False,
            'event_videocall_source': False,
            'show_avatars': True,
            'staff_user_ids': [(6, 0, [self.env.user.id])],
        }

    @api.model
    def _prepare_video_call_template_values(self):
        return {
            'allow_guests': True,
            'appointment_duration': 0.5,
            'slot_creation_interval': 0.5,
            'is_auto_assign': False,
            'is_date_first': False,
            'location_id': False,
            'name': _('Video Call'),
            'question_ids': [(0, 0, {
                'name': _('Describe what you need'),
                'question_type': 'text',
            })],
            'show_avatars': False,
        }

    @api.model
    def _prepare_table_booking_template_values(self):
        return {
            'appointment_duration': 2.0,
            'slot_creation_interval': 0.5,
            'is_auto_assign': True,
            'event_videocall_source': False,
            'hide_duration': True,
            'location_id': self.env.company.partner_id.id,
            'min_cancellation_hours': 1,
            'max_schedule_days': 45,
            'min_schedule_hours': 1.0,
            'name': _('Table'),
            'question_ids': [(0, 0, {
                'name': _('Do you have any dietary preferences or restrictions ?'),
                'placeholder': _('e.g. Vegetarian, Lactose Intolerant, ...'),
                'question_type': 'text',
            })],
            'resource_ids': [
                (0, 0, {
                    'name': _('Table %s', number),
                    'capacity': capacity,
                }) for number, capacity in enumerate([2, 2, 4, 6], start=1)
            ],
            'manage_capacity': True,
            'slot_ids': [
                (0, 0, {
                    'weekday': str(weekday),
                    'start_hour': start_hour,
                    'end_hour': end_hour,
                })
                for (start_hour, end_hour) in [(12, 14.5), (19, 0)]
                for weekday in range(2, 7)
            ],
            'schedule_based_on': 'resources',
            'staff_user_ids': [],
        }

    @api.model
    def _prepare_book_resource_template_values(self):
        return {
            'allow_guests': True,
            'appointment_duration': 1.0,
            'event_videocall_source': False,
            'is_auto_assign': False,
            'is_date_first': True,
            'location_id': self.env.company.partner_id.id,
            'min_cancellation_hours': 1,
            'max_schedule_days': 45,
            'min_schedule_hours': 1.0,
            'name': _('Book a Resource'),
            'resource_ids': [
                (0, 0, {
                    'name': _('Resource %s', number),
                }) for number in range(1, 5)
            ],
            'schedule_based_on': 'resources',
            'staff_user_ids': [],
        }
