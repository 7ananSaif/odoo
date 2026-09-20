# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class CalendarEvent(models.Model):
    _name = 'calendar.event'
    _inherit = 'calendar.event'

    @api.model
    def _send_table_notifications(self, events, command):
        today = fields.Date.today()
        fields_to_read = self._load_pos_data_fields(0)

        for event in events:
            # Don't include the event if it's not for today
            if event.start.date() != today:
                continue

            event_dict = event.read(fields_to_read, load=False)[0]
            event_appointment_type_id = event_dict.get('appointment_type_id')
            # tables that are booked for this event
            event_table_ids = event.booking_line_ids.appointment_resource_id.sudo().pos_table_ids
            for table in event_table_ids:
                for config in table.floor_id.pos_config_ids:
                    session = config.current_session_id

                    if (
                        session
                        and config.appointment_type_id
                        and config.appointment_type_id.id == event_appointment_type_id
                    ):
                        config._notify(("TABLE_BOOKING", {
                            "command": command,
                            "event": event_dict,
                        }))

    @api.model_create_multi
    def create(self, vals_list):
        new_events = super().create(vals_list)
        self._send_table_notifications(new_events, "ADDED")
        return new_events

    def write(self, vals):
        self._send_table_notifications(self, "REMOVED")
        result = super().write(vals)
        self._send_table_notifications(self, "ADDED")
        return result

    def unlink(self):
        self._send_table_notifications(self, "REMOVED")
        return super().unlink()

    @api.model
    def _appointment_resource_domain(self, data):
        if data['pos.config'][0]['module_pos_restaurant']:
            return [
                ('booking_line_ids.appointment_resource_id', 'in', [table['appointment_resource_id'] for table in data['restaurant.table']])
            ]
        else:
            return super()._appointment_resource_domain(data)
