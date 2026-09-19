# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api


class AppointmentResource(models.Model):
    _name = 'appointment.resource'
    _inherit = ['appointment.resource', 'pos.load.mixin']

    # this should be one2one
    pos_table_ids = fields.One2many('restaurant.table', 'appointment_resource_id', string='POS Table')
    is_used = fields.Json("Is Used", compute='_compute_is_used', help="Indicates if the resource is currently used in a calendar event for the given date range.")

    @api.model
    def _load_pos_data_domain(self, data, config):
        if not config.module_pos_restaurant:
            return False

        return [('pos_table_ids', 'in', [table['id'] for table in data['restaurant.table']])]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['pos_table_ids']

    def _compute_is_used(self):
        start_date_str = self.env.context.get('start_date')
        if not start_date_str:
            self.is_used = {}
            return
        start_datetime = fields.Datetime.from_string(start_date_str)
        start_of_day = start_datetime.replace(hour=0, minute=0, second=0)
        end_of_day = start_datetime.replace(hour=23, minute=59, second=59)
        if not start_datetime:
            self.is_used = {}
            return

        events = self.env['calendar.event'].search([
            ('resource_ids', 'in', self.ids),
            ('start', '<', end_of_day),
            ('stop', '>', start_of_day),
        ])
        for resource in self:
            appointment_type_id = resource.appointment_type_ids[0].id if resource.appointment_type_ids else False
            if not appointment_type_id:
                continue

            resource_events = events.filtered(
                lambda e: (
                    e.appointment_type_id
                    and e.appointment_type_id.id == appointment_type_id
                    and resource.id in e.appointment_resource_ids.ids
                )
            )

            event_start = resource_events[0].start.strftime("%Y-%m-%d %H:%M:%S") if resource_events else ''
            event_stop = resource_events[0].stop.strftime("%Y-%m-%d %H:%M:%S") if resource_events else ''
            capacity = resource_events[0].waiting_list_capacity if resource_events else ''
            resource.is_used = {
                'event_start': event_start,
                'event_stop': event_stop,
                'capacity': capacity
            } if resource_events else {}
