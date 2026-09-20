# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import datetime
from itertools import tee, chain

import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, models
from odoo.fields import Domain
from odoo.tools.intervals import Intervals
from odoo.tools.date_utils import localized


class HrWorkEntry(models.Model):
    _inherit = "hr.work.entry"

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=None, progress_bar_fields=None, start_date=None, stop_date=None, scale=None):
        """
        We override get_gantt_data to allow the display of open-ended records,
        We also want to add in the gantt rows, the active emloyees that have a check in in the previous 60 days
        """
        start_date = self.env.context.get('gantt_start_date') or start_date
        stop_date = self.env.context.get('gantt_stop_date') or stop_date
        additional_domain = Domain(domain) & Domain(self.env.context.get('active_domain') or Domain.TRUE)
        domain = additional_domain & Domain("date", "<", stop_date) & Domain("date", ">=", start_date)
        gantt_data = super().get_gantt_data(domain, groupby, read_specification, limit=limit, offset=offset, unavailability_fields=unavailability_fields, progress_bar_fields=progress_bar_fields, start_date=start_date, stop_date=stop_date, scale=scale)

        if groupby and groupby[0] == 'employee_id':
            employees_in_contract_ids = self.env["hr.employee"]._get_contract_versions(date_start=start_date, date_end=stop_date).keys()
            employees_with_work_entries_ids = [group['employee_id'][0] for group in gantt_data['groups']]
            employees_without_work_entries_ids = employees_in_contract_ids - employees_with_work_entries_ids

            employees_without_work_entries_domain = additional_domain & Domain('employee_id', 'in', employees_without_work_entries_ids)
            gantt_data_employee_without_work_entries = super().get_gantt_data(employees_without_work_entries_domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=unavailability_fields, progress_bar_fields=progress_bar_fields, start_date=start_date, stop_date=stop_date, scale=scale)
            for group in gantt_data_employee_without_work_entries['groups']:
                del group['__record_ids']  # Records are not needed here
                gantt_data['groups'].append(group)
                gantt_data['length'] += 1
            if unavailability_fields:
                for field in gantt_data['unavailabilities']:
                    gantt_data['unavailabilities'][field] |= gantt_data_employee_without_work_entries['unavailabilities'][field]
        return gantt_data

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):

        employees_by_calendar = defaultdict(lambda: self.env['hr.employee'])
        employees = self.env['hr.employee'].browse(res_ids)

        # Retrieve for each employee, their period linked to their calendars
        calendar_periods_by_employee = employees._get_calendar_periods(
            localized(start),
            localized(stop),
        )

        full_interval_UTC = Intervals([(
            start.astimezone(pytz.utc),
            stop.astimezone(pytz.utc),
            self.env['resource.calendar'],
        )])

        # calculate the intervals not covered by employee-specific calendars.
        # store these uncovered intervals for each employee.
        # store by calendar, employees involved with them
        periods_without_calendar_by_employee = defaultdict(list)
        for employee, calendar_periods in calendar_periods_by_employee.items():
            employee_interval_UTC = Intervals([])
            for (start, stop, calendar) in calendar_periods:
                calendar_periods_interval_UTC = Intervals([(
                    start.astimezone(pytz.utc),
                    stop.astimezone(pytz.utc),
                    self.env['resource.calendar'],
                )])
                employee_interval_UTC |= calendar_periods_interval_UTC
                employees_by_calendar[calendar] |= employee
            interval_without_calendar = full_interval_UTC - employee_interval_UTC
            if interval_without_calendar:
                periods_without_calendar_by_employee[employee.id] = interval_without_calendar

        # retrieve, for each calendar, unavailability periods for employees linked to this calendar
        unavailable_intervals_by_calendar = {}
        for calendar, employees in employees_by_calendar.items():
            # In case the calendar is not set (fully flexible calendar), we consider the employee as always available
            if not calendar or calendar.flexible_hours:
                unavailable_intervals_by_calendar[calendar] = {
                    employee.id: Intervals([])
                    for employee in employees
                }
                continue

            calendar_work_intervals = calendar._work_intervals_batch(
                localized(start),
                localized(stop),
                resources=employees.resource_id,
                tz=pytz.timezone(calendar.tz)
            )
            full_interval = Intervals([(
                start.astimezone(pytz.timezone(calendar.tz)),
                stop.astimezone(pytz.timezone(calendar.tz)),
                calendar
            )])
            unavailable_intervals_by_calendar[calendar] = {
                employee.id: full_interval - calendar_work_intervals[employee.resource_id.id]
                for employee in employees}

        # calculate employee's unavailability periods based on his calendar's periods
        # (e.g. calendar A on monday and tuesday and calendar b for the rest of the week)
        unavailable_intervals_by_employees = {}
        for employee, calendar_periods in calendar_periods_by_employee.items():
            employee_unavailable_full_interval = Intervals([])
            for (start, stop, calendar) in calendar_periods:
                interval = Intervals([(start, stop, self.env['resource.calendar'])])
                calendar_unavailable_interval_list = unavailable_intervals_by_calendar[calendar][employee.id]
                employee_unavailable_full_interval |= interval & calendar_unavailable_interval_list
            unavailable_intervals_by_employees[employee.id] = employee_unavailable_full_interval

        flexible_employees = self.env['hr.employee']
        for calendar, employees in employees_by_calendar.items():
            if calendar.flexible_hours:
                flexible_employees |= employees

        result = {}
        for employee_id in res_ids:
            # When an employee doesn't have any calendar,
            # he is considered unavailable for the entire interval
            if employee_id not in unavailable_intervals_by_employees:
                result[employee_id] = [{
                    'start': start.astimezone(pytz.utc),
                    'stop': stop.astimezone(pytz.utc),
                }]
                continue

            # When an employee has a flexible calendar,
            # he is considered available for the entire interval
            if employee_id in flexible_employees.ids:
                result[employee_id] = []
                continue

            # When an employee doesn't have a calendar for a part of the entire interval,
            # he will be unavailable for this part
            if employee_id in periods_without_calendar_by_employee:
                unavailable_intervals_by_employees[employee_id] |= periods_without_calendar_by_employee[employee_id]
            result[employee_id] = [{
                'start': interval[0].astimezone(pytz.utc),
                'stop': interval[1].astimezone(pytz.utc),
            } for interval in unavailable_intervals_by_employees[employee_id]]

        return result

    @api.model
    def _gantt_progress_bar(self, field, res_ids, start, stop):
        all_versions = self.env['hr.employee'].browse(res_ids)._get_all_versions_with_contract_overlap_with_period(start, stop)
        intervals_to_search = defaultdict(lambda: self.env['hr.version'])
        values = defaultdict(lambda: {'value': 0, 'max_value': 0, 'value_per_day': defaultdict(float), 'max_per_day': defaultdict(float)})

        # Max duration value fetch
        all_version_normal, all_version_shifted = tee(all_versions.sorted(lambda v: (v.employee_id, v.date_version)))
        next(all_version_shifted, None)
        all_version_shifted = chain(all_version_shifted, [None])
        for current_version, next_version in zip(all_version_normal, all_version_shifted):
            temp_start = start
            temp_stop = stop
            if next_version and next_version.employee_id == current_version.employee_id:
                # If the employee has multiple versions
                if current_version.date_version < next_version.date_version < start.date():
                    continue
                if next_version.date_version < stop.date():
                    # limit the interval stop with the version validity
                    temp_stop = datetime.combine(next_version.date_version, datetime.min.time(), pytz.utc)
            if current_version.contract_date_end and current_version.contract_date_end < stop.date():
                # limit the interval stop with the contract validity
                temp_stop = datetime.combine(current_version.contract_date_end, datetime.min.time(), pytz.utc) + relativedelta(days=1)
            if current_version.date_version >= start.date():
                # limit the interval start with the version date if it's after the start date
                temp_start = datetime.combine(current_version.date_version, datetime.min.time(), pytz.utc)
            intervals_to_search[temp_start, temp_stop] |= current_version

        # The same behavior as work entry generation (batch per intervals) due to issues with _get_attendance_intervals
        # method makes a batch per all versions impossible for the whole date range
        for interval, versions in intervals_to_search.items():
            date_from, date_to = interval
            for work_entry_value in self.env["hr.version"]._generate_work_entries_postprocess(versions._get_work_entries_values(date_from, date_to)):
                if work_entry_value['date'] < stop.date():
                    values[work_entry_value['employee_id']]['max_value'] += work_entry_value["duration"]
                    values[work_entry_value['employee_id']]['max_per_day'][str(work_entry_value['date'])] += work_entry_value["duration"]

        # Current durations
        work_entries = self._read_group(
            domain=[
                (field, 'in', res_ids),
                ["date", "<", stop],
                ["date", ">=", start]
            ],
            groupby=[field, "date:day"],
            aggregates=["duration:sum"]
        )

        for employee, date, duration in work_entries:
            values[employee.id]['value'] += duration
            values[employee.id]['value_per_day'][str(date)] += duration
            values[employee.id]['max_value'] = values[employee.id]['max_value']

        return values
