# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from collections import defaultdict
import pytz

from odoo import api, fields, models
from odoo.tools.intervals import Intervals


class HrVersion(models.Model):
    _inherit = 'hr.version'

    work_entry_source = fields.Selection(
        selection_add=[('planning', 'Planning')],
        ondelete={'planning': 'set default'},
    )

    def _get_more_vals_attendance_interval(self, interval):
        result = super()._get_more_vals_attendance_interval(interval)
        if interval[2]._name == 'planning.slot':
            # Due to how Intervals work we might lose the right start and end time for our work entry
            # i.e. [(1, 5, slot_1), (3, 10, slot_2)] will result in (1, 10, {slot_1, slot_2})
            # `_get_version_work_entries_values` already takes care of unsplitting our invervals into two for that case
            # But the date needs to be correct after the fact, which we do here.
            # We still take the interval's date in case it was pushed by start_dt/end_dt.
            slot = interval[2]
            # Avoid timezone conversions
            subresult = [('planning_slot_id', slot.id)]
            if interval[0] < pytz.utc.localize(slot.start_datetime):
                subresult.append(('date_start', slot.start_datetime))
            if interval[1] > pytz.utc.localize(slot.end_datetime):
                subresult.append(('date_stop', slot.end_datetime))
            result.extend(subresult)
        return result

    def _get_attendance_intervals(self, start_dt, end_dt):
        planning_based_contracts = self.filtered(lambda c: c.work_entry_source == 'planning')
        search_domain = [
            ('employee_id', 'in', planning_based_contracts.employee_id.ids),
            ('state', '=', 'published'),
            ('start_datetime', '<', end_dt.replace(tzinfo=None)),
            ('end_datetime', '>', start_dt.replace(tzinfo=None)),
        ]
        resource_ids = planning_based_contracts.employee_id.resource_id.ids
        planning_slots = self.env['planning.slot'].sudo().search(search_domain) if planning_based_contracts\
            else self.env['planning.slot']
        intervals = defaultdict(list)
        for planning_slot in planning_slots:
            intervals[planning_slot.resource_id.id].append((
                max(start_dt, pytz.utc.localize(planning_slot.start_datetime)),
                min(end_dt, pytz.utc.localize(planning_slot.end_datetime)),
                planning_slot))
        mapped_intervals = {r: Intervals(intervals[r], keep_distinct=True) for r in resource_ids}
        mapped_intervals.update(super()._get_attendance_intervals(start_dt, end_dt))
        return mapped_intervals

    @api.model
    def _generate_work_entries_postprocess(self, vals_list):
        new_vals_list = []
        for vals in vals_list:
            if not vals.get('planning_slot_id') or not vals.get('date_start') or not vals.get('date_stop'):
                new_vals_list.append(vals)
                continue
            dt_start = vals.pop('date_start')
            dt_stop = vals.pop('date_stop')
            date_start = dt_start.date()
            date_stop = dt_stop.date()
            slot = self.env['planning.slot'].browse(vals['planning_slot_id'])
            number_of_days = (date_stop - date_start).days + 1
            allocated_hours = slot._get_planning_duration(dt_start, dt_stop)
            for i in range(number_of_days):
                new_vals = vals.copy()
                new_vals['date'] = date_start + timedelta(days=i)
                new_vals['duration'] = allocated_hours / number_of_days
                new_vals_list.append(new_vals)
        return super()._generate_work_entries_postprocess(new_vals_list)
