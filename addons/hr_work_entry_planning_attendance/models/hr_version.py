# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import models
from odoo.tools.intervals import Intervals


class HrOvertimeRule(models.Model):
    _inherit = 'hr.attendance.overtime.rule'
    _name = 'hr.attendance.overtime.rule'

    def _get_expected_hours_from_contract(self, date, version, period='day'):
        if version.work_entry_source == 'planning' and version.overtime_from_attendance:
            date_start = date
            date_end = date
            if period == 'week':
                date_start = date_start - relativedelta(days=date_start.weekday())  # Set to Monday
                date_end = date_start + relativedelta(days=6)  # Set to Sunday
            start_dt = datetime.combine(date_start, datetime.min.time())
            end_dt = datetime.combine(date_end, datetime.max.time())
            search_domain = [
                ('employee_id', '=', version.employee_id.id),
                ('state', '=', 'published'),
                ('start_datetime', '<', end_dt.replace(tzinfo=None)),
                ('end_datetime', '>', start_dt.replace(tzinfo=None)),
            ]
            planning_slots = self.env['planning.slot'].sudo().search(search_domain)
            expected_hours = sum(planning_slots.mapped('duration'))

            return expected_hours
        return super()._get_expected_hours_from_contract(date, version, period='day')


class HrVersion(models.Model):
    _inherit = 'hr.version'
    _name = 'hr.version'

    def _get_attendance_intervals(self, start_dt, end_dt):
        ##################################
        #   PLANNING BASED CONTRACTS WITH ATTENDANCE OVERTIME  #
        ##################################
        mapped_intervals = super()._get_attendance_intervals(start_dt, end_dt)
        planning_based_contracts = self.filtered(lambda c: c.work_entry_source == 'planning' and c.overtime_from_attendance)
        attendances = self.env['hr.attendance'].sudo().search([
            ('employee_id', 'in', planning_based_contracts.employee_id.ids),
            ('check_in', '<=', end_dt.replace(tzinfo=None)),
            ('check_out', '>=', start_dt.replace(tzinfo=None)),  # We ignore attendances which don't have a check_out
        ])
        overtime_intervals = {r: Intervals(keep_distinct=True) for r in mapped_intervals}
        overtime_intervals.update(planning_based_contracts._get_overtime_intervals(start_dt, end_dt))
        planning_based_contracts._set_real_overtime_intervals(start_dt, end_dt, attendances, mapped_intervals, overtime_intervals)
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
