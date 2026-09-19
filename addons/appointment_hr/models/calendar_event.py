# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models
from odoo.tools.intervals import Intervals
from odoo.tools.date_utils import localized


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        result = super()._gantt_unavailability(field, res_ids, start, stop, scale)

        # skip if not dealing with appointments
        if field != 'partner_ids':
            return result

        start = localized(start)
        stop = localized(stop)

        partners = self.env['res.partner'].browse(res_ids)
        users = partners.user_ids
        users_from_partner_id = users.grouped(lambda user: user.partner_id.id)

        calendars = users.employee_id.resource_calendar_id
        employee_by_calendar = users.employee_id.grouped('resource_calendar_id')
        unavailabilities_by_calendar = {
            calendar: calendar._unavailable_intervals_batch(
                start, stop,
                resources=employee_by_calendar[calendar].resource_id
            ) for calendar in calendars
        }

        event_unavailabilities = self._gantt_unavailabilities_events(start, stop, partners)

        for partner_id in res_ids:
            attendee_users = users_from_partner_id.get(partner_id, self.env['res.users'])
            attendee = partners.filtered(lambda partner: partner.id == partner_id)

            # calendar leaves
            unavailabilities = Intervals([
                (unavailability['start'], unavailability['stop'], self.env['res.partner'])
                for unavailability in result.get(partner_id, [])
            ])
            unavailabilities |= event_unavailabilities.get(attendee.id, Intervals([]))
            for user in attendee_users.filtered('employee_resource_calendar_id'):
                calendar_leaves = unavailabilities_by_calendar[user.employee_resource_calendar_id]
                unavailabilities |= Intervals([
                    (start, end, attendee)
                    for start, end in calendar_leaves.get(user.employee_id.resource_id.id, [])])
            result[partner_id] = [{'start': start, 'stop': stop} for start, stop, _ in unavailabilities]
        return result
