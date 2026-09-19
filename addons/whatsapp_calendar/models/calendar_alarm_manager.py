from odoo import api, models


class AlarmManager(models.AbstractModel):
    _inherit = 'calendar.alarm_manager'

    @api.model
    def _send_reminder(self):
        """ Cron method, overridden here to send WhatsApp reminders as well
        """
        super()._send_reminder()
        events_by_alarm = self._get_events_by_alarm_to_notify('whatsapp')
        if not events_by_alarm:
            return

        for alarm_id, event_ids in events_by_alarm.items():
            alarm = self.env['calendar.alarm'].with_prefetch([alarm_id]).browse(alarm_id)
            events = self.env['calendar.event'].with_prefetch(event_ids).browse(event_ids)
            # Filter out the event organizer when notify_responsible is False
            attendees = events.attendee_ids.filtered(
                lambda attendee: attendee.state != 'declined' and (
                    alarm.notify_responsible or attendee.partner_id != attendee.event_id.user_id.partner_id
                )
            )

            if attendees:
                self.env['whatsapp.composer'].create({
                    'batch_mode': True,
                    'res_ids': attendees.ids,
                    'res_model': attendees._name,
                    'wa_template_id': alarm.wa_template_id.id
                })._send_whatsapp_template(force_send_by_cron=True)

            events._setup_event_recurrent_alarms(events_by_alarm)
