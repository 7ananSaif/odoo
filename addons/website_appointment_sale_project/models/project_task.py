# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    calendar_event_id = fields.Many2one('calendar.event', string='Calendar Event', copy=False, help="Linked appointment of this task")

    def action_view_appointment(self):
        """
        action to open the appointment form view (calendar_event form view)
        action should be only visible if there is at least 1 appointment, and allow_billable is true on the project
        it should disable the creation of new records
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Appointment'),
            'res_model': 'calendar.event',
            'res_id': self.calendar_event_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('calendar.view_calendar_event_form').id,
            'target': 'current',
            'context': {'create': False},
        }
