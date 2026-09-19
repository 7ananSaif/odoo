from odoo import models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    def _get_trigger_alarm_types(self):
        return super()._get_trigger_alarm_types() + ['whatsapp']
