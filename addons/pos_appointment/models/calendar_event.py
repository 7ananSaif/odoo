# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from datetime import timedelta


class CalendarEvent(models.Model):
    _name = 'calendar.event'
    _inherit = ["calendar.event", "pos.load.mixin"]

    answers = fields.Char('Q&A answers', compute='_compute_answers')
    phone_number = fields.Char(string='Phone number')
    appointment_status = fields.Selection(group_expand='_read_group_appointment_status')
    waiting_list_capacity = fields.Integer(string='Waiting List Capacity', compute='_compute_waiting_list_capacity', store=True, readonly=False)

    @api.model
    def _read_group_appointment_status(self, status, domain):
        return ['booked', 'attended', 'no_show']

    @api.depends('appointment_answer_input_ids')
    def _compute_answers(self):
        for record in self:
            record.answers = (', ').join([answer.value_text_box or answer.value_answer_id.name for answer in record.appointment_answer_input_ids.sorted('id')])

    def _appointment_resource_domain(self, data):
        return [('booking_line_ids.appointment_resource_id', '=', False)]

    @api.model
    def _load_pos_data_domain(self, data, config):
        now = fields.Datetime.now()
        day_after = fields.Date.today() + timedelta(days=1)
        return (
            self._appointment_resource_domain(data)
            + [
                ('appointment_type_id', '=', config.appointment_type_id.id),
                '|', '&', ('start', '>=', now), ('start', '<=', day_after), '&', ('stop', '>=', now), ('stop', '<=', day_after),
            ]
        )

    @api.model
    def _load_pos_data_fields(self, config):
        return ['id', 'start', 'duration', 'stop', 'name', 'appointment_type_id', 'appointment_status', 'appointment_resource_ids', 'total_capacity_reserved']

    def action_open_booking_gantt_view(self):
        return {
            'name': _('Manage Bookings'),
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            "views": [
                (self.env.ref("pos_appointment.calendar_event_view_kanban").id, 'kanban'),
                (self.env.ref("pos_appointment.calendar_event_view_gantt_booking_resource").id, "gantt"),
                (self.env.ref("pos_appointment.calendar_event_view_tree").id, 'list'),
                (self.env.ref("pos_appointment.calendar_event_view_calendar").id, 'calendar'),
                (False, 'pivot'),
                (self.env.ref("pos_appointment.calendar_event_view_form_gantt_booking").id, 'form'),
                (self.env.ref("pos_appointment.calendar_event_view_graph_pos_appointment").id, 'graph'),
            ],
            'target': 'current',
            'context': {
                'appointment_booking_gantt_show_all_resources': True,
                'active_model': 'appointment.type',
                'default_partner_ids': [],
                'default_duration': 2,
                'default_total_capacity_reserved': 0,
                'default_waiting_list_capacity': 2,
                "search_default_appointment_type_id": self.env.context.get("appointment_type_id"),
                "no_breadcrumbs": True,
                'hide_no_content_helper': True,
                'from_pos_booking': True,
                "appointment_type_id": self.env.context.get("appointment_type_id"),
            }
        }

    def action_open_booking_form_view(self):
        return {
            'name': _('Edit Booking'),
            'target': 'new',
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'views': [(self.env.ref('pos_appointment.calendar_event_view_form_gantt_booking').id, 'form')],
            'res_id': self.id,
        }

    def action_create_booking_form_view(self, appointment_type_id):
        return {
            'name': _('Create Booking'),
            'target': 'new',
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'views': [(self.env.ref('pos_appointment.calendar_event_view_form_gantt_booking').id, 'form')],
            'context': {
                'default_appointment_type_id': appointment_type_id,
                'default_total_capacity_reserved': 0,
                'default_waiting_list_capacity': 2,
            }
        }

    @api.depends('resource_ids', 'total_capacity_reserved')
    def _compute_waiting_list_capacity(self):
        for event in self:
            # always sync if capacity is managed
            if event.appointment_type_schedule_based_on == 'resources' and event.appointment_type_manage_capacity:
                event.waiting_list_capacity = event.total_capacity_reserved
            # otherwise only set a default from reserved capacity and let users edit it
            elif not event.waiting_list_capacity:
                if event.total_capacity_reserved:
                    event.waiting_list_capacity = event.total_capacity_reserved
                elif event.resource_ids:
                    event.waiting_list_capacity = sum(event.resource_ids.mapped('capacity'))
                else:
                    event.waiting_list_capacity = 0

    def set_attended(self):
        self.appointment_status = 'attended'

    def set_cancelled(self):
        self.appointment_status = 'cancelled'
