# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pytz import timezone, utc

from odoo import api, fields, models
from odoo.tools.intervals import Intervals


class HrVersion(models.Model):
    _inherit = 'hr.version'

    work_entry_source = fields.Selection(
        selection_add=[('attendance', 'Attendances')],
        ondelete={'attendance': 'set default'},
    )
    overtime_from_attendance = fields.Boolean(
        "Extra hours", help="Add extra hours from attendances to the working entries", store=True, tracking=True,
        readonly=False, compute='_compute_overtime_from_attendance', groups="hr.group_hr_manager")

    def _get_overtime_intervals(self, start_dt, end_dt):
        start_naive = start_dt.replace(tzinfo=None)
        end_naive = end_dt.replace(tzinfo=None)

        overtimes = self.env['hr.attendance.overtime.line']._read_group(
            domain=[
                ('employee_id', 'in', self.employee_id.ids),
                ('date', '<=', end_naive.date()),
                ('date', '>=', start_naive.date()),
                ('manual_duration', '>', 0),
            ],
            groupby=['employee_id', 'date:day'],
            aggregates=['id:recordset']
        )
        overtimes_by_employee_by_date = defaultdict(dict)
        for employee, date, overtime_lines in overtimes:
            overtimes_by_employee_by_date[employee][date] = overtime_lines
        res = {}
        for employee, overtimes_by_date in overtimes_by_employee_by_date.items():
            resource = employee.resource_id
            for day, overtimes in overtimes_by_date.items():
                overtime_list = []
                for (check_in, check_out), ots in overtimes.grouped(lambda ot: (ot.time_start, ot.time_stop)).items():
                    prev_duration = 0  # to avoid intervals overlapping
                    for ot in ots:
                        datetime_stop = min(
                            datetime.combine(ot.date, datetime.max.time()),
                            ot.time_stop
                        ) - relativedelta(hours=prev_duration)
                        datetime_start = datetime_stop - timedelta(hours=ot.duration)
                        prev_duration += ot.duration
                        overtime_list.append((utc.localize(datetime_start), utc.localize(datetime_stop), ot))
            res[resource.id] = Intervals(overtime_list, keep_distinct=True)
        return res

    def _set_real_overtime_intervals(self, start_dt, end_dt, attendances, mapped_intervals, overtime_intervals):
        """ This method split the overtime_intervals to not overlap the expected employee schedule or planning
        Example: Working schedule : 8h-12h -> 13h-17h, Attendance = 7h-18h, Overtime duration = 2h
        overtime_intervals will be equal to 16h-18h (because we only want to display one overtime line)
        but the real overtime intervals is equal to 7h-8h and 17h-18h
        """
        attendances_by_resources = attendances.grouped(lambda attendance: attendance.employee_id.resource_id.id)
        lunch_by_resource = defaultdict()
        version_by_resource_calendar = self.grouped('resource_calendar_id')
        for calendar, versions in version_by_resource_calendar.items():
            if not calendar:
                continue
            lunch_by_resource.update(calendar._attendance_intervals_batch(start_dt, end_dt, resources=versions.employee_id.resource_id, lunch=True))
        for resource in mapped_intervals:
            attendance_overtime_intersection = overtime_intervals[resource] & mapped_intervals[resource]
            if not attendance_overtime_intersection:
                continue
            resource_attendance_intervals = Intervals([(
                utc.localize(att.check_in), utc.localize(att.check_out), self.env['hr.attendance']
            ) for att in attendances_by_resources[resource]])
            relevant_attendance_interval = resource_attendance_intervals & Intervals([(start_dt, end_dt, self.env['hr.attendance'])])
            left_overtime_intervals = relevant_attendance_interval - overtime_intervals[resource] - mapped_intervals[resource] - lunch_by_resource[resource]
            if not left_overtime_intervals:
                continue
            diff_hours = (attendance_overtime_intersection._items[0][0] - left_overtime_intervals._items[0][0]).total_seconds() / 3600
            attendance_overtime_intersection = Intervals([(
                start - timedelta(hours=diff_hours),
                stop - timedelta(hours=diff_hours),
                model
            ) for start, stop, model in attendance_overtime_intersection])
            overtime_intervals[resource] = (overtime_intervals[resource] | attendance_overtime_intersection) - mapped_intervals[resource]

    def _get_attendance_intervals(self, start_dt, end_dt):
        ##################################
        #   ATTENDANCE BASED CONTRACTS   #
        ##################################
        start_naive = start_dt.replace(tzinfo=None)
        end_naive = end_dt.replace(tzinfo=None)
        overtime_contracts = self.filtered_domain(['|', ('work_entry_source', '=', 'attendance'), ('ruleset_id', '!=', False)])
        attendance_based_contracts = self.filtered_domain([('work_entry_source', '=', 'attendance')])
        search_domain = [
            ('employee_id', 'in', overtime_contracts.employee_id.ids),
            ('check_in', '<=', end_naive),
            ('check_out', '>=', start_naive),  # We ignore attendances which don't have a check_out
        ]
        resource_ids = attendance_based_contracts.employee_id.resource_id.ids
        all_attendances = self.env['hr.attendance'].sudo().search(search_domain)
        attendances = all_attendances.filtered_domain([('employee_id.work_entry_source', '=', 'attendance')]) if attendance_based_contracts\
            else self.env['hr.attendance']
        intervals = defaultdict(list)
        calendar_by_employee = {}
        leaves = {}
        lunches = {}
        employee_by_calendar = defaultdict(lambda: self.env['hr.employee'])
        for version in self:
            calendar = version.resource_calendar_id
            if calendar and not calendar.flexible_hours:
                calendar_by_employee[version.employee_id] = calendar
                employee_by_calendar[calendar] += version.employee_id
        for calendar, employees in employee_by_calendar.items():
            leaves |= calendar._leave_intervals_batch(start_dt, end_dt, resources=employees.resource_id)
            lunches |= calendar._attendance_intervals_batch(start_dt, end_dt, resources=employees.resource_id, lunch=True)
        for attendance in attendances:
            resource = attendance.employee_id.resource_id
            tz = timezone(attendance.employee_id.tz or resource.tz)    # refer to resource's tz if fully flexible resource (calendar is False)
            check_in_tz = attendance.check_in.astimezone(tz)
            check_out_tz = attendance.check_out.astimezone(tz)
            if attendance.overtime_status == 'refused':
                check_out_tz -= timedelta(hours=attendance.validated_overtime_hours)

            resource_lunch = lunches.get(attendance.employee_id.resource_id.id, Intervals([]))
            resource_leave = leaves.get(attendance.employee_id.resource_id.id, Intervals([]))
            real_lunch_intervals = resource_lunch - resource_leave
            attendance_intervals = Intervals([(check_in_tz, check_out_tz, attendance)]) - real_lunch_intervals
            for interval in attendance_intervals:
                intervals[resource.id].append((
                    max(start_dt, interval[0]),
                    min(end_dt, interval[1]),
                    attendance))

        mapped_intervals = {r: Intervals(intervals[r], keep_distinct=True) for r in resource_ids}
        mapped_intervals.update(super()._get_attendance_intervals(
            start_dt, end_dt))

        working_schedule_versions = self.filtered(lambda v: v.work_entry_source == 'calendar')
        if working_schedule_versions:
            working_schedule_search_domain = [
                ('employee_id', 'in', working_schedule_versions.employee_id.ids),
                ('check_in', '<', end_naive),
                ('check_out', '>', start_naive),
            ]
            working_schedule_attendances = self.env['hr.attendance'].sudo().search(working_schedule_search_domain)

            for attendance in working_schedule_attendances:
                if not attendance.overtime_hours or not attendance.employee_id.version_id.overtime_from_attendance:
                    continue
                version = working_schedule_versions.filtered(
                    lambda v: v.employee_id == attendance.employee_id
                    and v.contract_date_start <= attendance.check_out.date()
                    and (not v.contract_date_end or v.contract_date_end >= attendance.check_in.date()))
                if not version:
                    continue
                version = version[0]  # take the first one
                tz = timezone(version.resource_calendar_id.tz or attendance.employee_id.tz or resource.tz)
                check_in_tz = attendance.check_in.astimezone(tz)
                check_out_tz = attendance.check_out.astimezone(tz)
                schedule_intervals = mapped_intervals[version.employee_id.resource_id.id]
                if schedule_intervals:
                    items = list(schedule_intervals)
                    matching_interval = next((interval for interval in items if interval[0].date() == check_in_tz.date()), None)
                    if matching_interval:
                        start, stop, recs = matching_interval
                        if check_in_tz < start:
                            idx = items.index(matching_interval)
                            items[idx] = (check_in_tz, stop, recs)
                            mapped_intervals[version.employee_id.resource_id.id] = Intervals(items, keep_distinct=True)

        overtime_intervals = {r: Intervals(keep_distinct=True) for r in mapped_intervals}
        overtime_intervals.update(overtime_contracts._get_overtime_intervals(start_dt, end_dt))
        overtime_attendances = all_attendances.filtered_domain([('employee_id.ruleset_id', '!=', False)])
        overtime_contracts._set_real_overtime_intervals(start_dt, end_dt, overtime_attendances, mapped_intervals, overtime_intervals)
        work_entry_overtime_intervals = defaultdict(list)
        for r, intervals in overtime_intervals.items():
            for start, end, overtime in intervals:
                if not (overtime.rule_ids.work_entry_type_id and overtime.status == 'approved'):
                    continue
                work_entry_overtime_intervals[r].extend([
                    (start, end, overtime)
                ])

        result = {
            r: (mapped_intervals[r] - overtime_intervals[r])
            | Intervals(work_entry_overtime_intervals[r], keep_distinct=True)
            for r in mapped_intervals
        }
        return result

    def _get_valid_leave_intervals(self, attendances, interval):
        self.ensure_one()
        badge_attendances = Intervals([
            (start, end, record) for (start, end, record) in attendances
            if start <= interval[1] and end > interval[0] and isinstance(record, self.env['hr.attendance'].__class__)
        ], keep_distinct=True)
        if badge_attendances:
            leave_interval = Intervals([interval], keep_distinct=True)
            return list(leave_interval - badge_attendances)
        return super()._get_valid_leave_intervals(attendances, interval)

    def _get_real_attendance_work_entry_vals(self, intervals):
        self.ensure_one()
        non_attendance_intervals = [interval for interval in intervals if interval[2]._name not in ['hr.attendance', 'hr.attendance.overtime.line']]
        attendance_intervals = [interval for interval in intervals if interval[2]._name in ['hr.attendance', 'hr.attendance.overtime.line']]
        if attendance_intervals:
            default_overtime_type = self.env.ref('hr_work_entry.work_entry_type_overtime')
            attendance_work_entry_type = self.env.ref('hr_work_entry.work_entry_type_attendance')
        vals = super()._get_real_attendance_work_entry_vals(non_attendance_intervals)

        employee = self.employee_id
        for interval in attendance_intervals:
            if interval[2]._name == 'hr.attendance':
                work_entry_type = attendance_work_entry_type
                # All benefits generated here are using datetimes converted from the employee's timezone
                vals += [dict([
                          ('name', "%s: %s" % (work_entry_type.name, employee.name)),
                          ('date_start', interval[0].astimezone(utc).replace(tzinfo=None)),
                          ('date_stop', interval[1].astimezone(utc).replace(tzinfo=None)),
                          ('work_entry_type_id', work_entry_type.id),
                          ('employee_id', employee.id),
                          ('version_id', self.id),
                          ('company_id', self.company_id.id),
                      ] + self._get_more_vals_attendance_interval(interval))]
            elif interval[2]._name == 'hr.attendance.overtime.line':
                overtime_mode = self.ruleset_id.rate_combination_mode
                overtime_line_id = interval[2]
                triggered_rule_work_entry_types = overtime_line_id.rule_ids.mapped('work_entry_type_id') or default_overtime_type

                # Take into account manually encoded duration
                date_start = interval[0].astimezone(utc).replace(tzinfo=None)
                date_stop = interval[1].astimezone(utc).replace(tzinfo=None)
                if overtime_mode == 'max' or len(triggered_rule_work_entry_types) == 1:
                    work_entry_type = max(triggered_rule_work_entry_types, key=lambda w: w.amount_rate)
                    # All benefits generated here are using datetimes converted from the employee's timezone
                    vals += [dict([
                              ('name', "%s: %s" % (work_entry_type.name, employee.name)),
                              ('date_start', date_start),
                              ('date_stop', date_stop),
                              ('work_entry_type_id', work_entry_type.id),
                              ('employee_id', employee.id),
                              ('version_id', self.id),
                              ('company_id', self.company_id.id),
                          ] + self._get_more_vals_attendance_interval(interval))]
                else:
                    for triggered_rule in overtime_line_id.rule_ids:
                        # All benefits generated here are using datetimes converted from the employee's timezone
                        vals += [dict([
                                  ('name', "%s: %s" % (triggered_rule.work_entry_type_id.name, employee.name)),
                                  ('date_start', date_start),
                                  ('date_stop', date_stop),
                                  ('work_entry_type_id', triggered_rule.work_entry_type_id.id),
                                  ('employee_id', employee.id),
                                  ('version_id', self.id),
                                  ('company_id', self.company_id.id),
                              ] + self._get_more_vals_attendance_interval(interval))]
        return vals

    def _get_more_vals_attendance_interval(self, interval):
        vals = super()._get_more_vals_attendance_interval(interval)
        if interval[2]._name == 'hr.attendance':
            vals.append(('attendance_id', interval[2].id))
        if interval[2]._name == 'hr.attendance.overtime.line':
            vals.append(('overtime_id', interval[2].id))
        return vals

    def _get_real_attendances(self, attendances, leaves, worked_leaves):
        attendances_list = []
        no_attendances_list = []
        for start, stop, model in attendances:
            if model._name in ['hr.attendance', 'hr.attendance.overtime.line']:
                attendances_list.append((start, stop, model))
            else:
                no_attendances_list.append((start, stop, model))
        super_list = super()._get_real_attendances(Intervals(no_attendances_list), leaves, worked_leaves)._items
        return Intervals(attendances_list + super_list, keep_distinct=True)

    @api.model
    def _get_whitelist_fields_from_template(self):
        return super()._get_whitelist_fields_from_template() + ['overtime_from_attendance']

    @api.depends('ruleset_id')
    def _compute_overtime_from_attendance(self):
        for record in self:
            record.overtime_from_attendance = bool(record.ruleset_id)
