
from odoo.tools.intervals import Intervals
from datetime import datetime, timedelta
from dateutil.rrule import rrule, DAILY
from odoo.tools.date_utils import sum_intervals
from pytz import timezone, utc
import copy

from odoo import models
from odoo.fields import Domain


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _get_schedules_by_employee_by_work_type(self, start, stop, version_periods_by_employee):
        res = super()._get_schedules_by_employee_by_work_type(start, stop, version_periods_by_employee)
        employee_schedule = copy.deepcopy(res['schedule'])
        planning_periods = []
        for employee, version_periods in version_periods_by_employee.items():
            for (begin, end, version) in version_periods:
                if version.work_entry_source == 'planning':
                    planning_periods.append([
                        ('state', '=', 'published'),
                        ('start_datetime', '<=', end.replace(tzinfo=None)),
                        ('end_datetime', '>=', begin.replace(tzinfo=None)),
                    ])
                    version_period = Intervals([(
                        begin.replace(tzinfo=None),
                        end.replace(tzinfo=None),
                        self.env['resource.calendar'])])
                    res['schedule'][employee]['work'] -= version_period
                    res['fully_flexible'][employee] -= version_period

        planning_slots_by_employee = dict(self.env['planning.slot'].sudo()._read_group(
            domain=Domain.AND([
                Domain('state', '=', 'published'),
                Domain.OR(planning_periods)
            ]),
            groupby=["employee_id"],
            aggregates=["id:recordset"]
        ))
        for employee, planning_slots in planning_slots_by_employee.items():
            planning_slot_interval = Intervals([])
            tz = timezone(employee.tz)
            for planning_slot in planning_slots:
                start = utc.localize(planning_slot.start_datetime).astimezone(tz).replace(tzinfo=None)
                stop = utc.localize(planning_slot.end_datetime).astimezone(tz).replace(tzinfo=None)
                allocated_percentage = planning_slot.allocated_percentage
                schedule_interval = employee_schedule[employee]['work'] & Intervals([(start, stop, self.env['resource.calendar'])])
                planning_intervals = Intervals([])
                if allocated_percentage == 100:
                    planning_intervals = schedule_interval
                else:
                    for day in rrule(DAILY, dtstart=start, until=stop):
                        day_start = max(datetime.combine(day, datetime.time.min()), start)
                        day_stop = min(datetime.combine(day, datetime.time.max()), stop)
                        full_duration = sum_intervals(schedule_interval & Intervals([(day_start, day_stop, self.env['resource.calendar'])]))
                        day_stop -= timedelta(hours=full_duration * (100 - allocated_percentage))
                        planning_intervals |= Intervals(day_start, day_stop, self.env['resource.calendar'])
                planning_slot_interval |= planning_intervals
            res['schedule'][employee]['work'] |= planning_slot_interval
        return res
