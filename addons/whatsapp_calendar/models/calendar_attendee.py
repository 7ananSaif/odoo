from odoo import models


class CalendarAttendee(models.Model):
    _inherit = 'calendar.attendee'

    def _whatsapp_get_responsible(self, related_message=False, related_record=False, whatsapp_account=False):
        responsible_user = self.event_id.user_id
        if responsible_user and responsible_user.active and responsible_user._is_internal() and not responsible_user._is_superuser():
            return responsible_user

        return super()._whatsapp_get_responsible(related_message, related_record, whatsapp_account)
