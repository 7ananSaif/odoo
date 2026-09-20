# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import re

from odoo.tests import freeze_time
from .test_common import TestCommon
from pytz import utc

from odoo import Command

@freeze_time('2020-01-01')
class TestPlanningLeaves(TestCommon):
    def test_simple_employee_leave(self):
        self.leave_type.responsible_ids = [Command.link(self.env.ref('base.user_admin').id)]
        self.leave_type.request_unit = 'day'
        leave = self.env['hr.leave'].sudo().create({
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': '2020-01-01',
            'request_date_to': '2020-01-01',
        })

        slot_1 = self.env['planning.slot'].create({
            'resource_id': self.resource_bert.id,
            'start_datetime': datetime.datetime(2020, 1, 1, 8, 0),
            'end_datetime': datetime.datetime(2020, 1, 1, 17, 0),
        })
        slot_2 = self.env['planning.slot'].create({
            'resource_id': self.resource_bert.id,
            'start_datetime': datetime.datetime(2020, 1, 2, 8, 0),
            'end_datetime': datetime.datetime(2020, 1, 2, 17, 0),
        })

        self.assertNotEqual(slot_1.leave_warning, False, "leave is not validated , but warning for requested time off")

        leave.action_approve()

        self.assertNotEqual(slot_1.leave_warning, False,
                            "employee is on leave, should have a warning")
        # The warning should display the whole concerned leave period
        (slot_1 + slot_2).invalidate_recordset(fnames=["leave_warning"])
        self.assertEqual(slot_1.leave_warning,
                         "bert is on time off on 01/01/2020. \n")

        self.assertEqual(slot_2.leave_warning, False,
                         "employee is not on leave, no warning")

    def test_multiple_leaves(self):
        self.env['hr.leave'].sudo().create({
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': '2020-01-06',
            'request_date_to': '2020-01-07',
        }).action_approve()

        self.env['hr.leave'].sudo().create({
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': '2020-01-08',
            'request_date_to': '2020-01-10',
        }).action_approve()

        slot_1 = self.env['planning.slot'].create({
            'resource_id': self.resource_bert.id,
            'start_datetime': datetime.datetime(2020, 1, 6, 8, 0),
            'end_datetime': datetime.datetime(2020, 1, 6, 17, 0),
        })

        self.assertNotEqual(slot_1.leave_warning, False,
                            "employee is on leave, should have a warning")
        # The warning should display the whole concerned leave period
        self.assertEqual(slot_1.leave_warning,
                         "bert is on time off from 01/06/2020 to 01/07/2020. \n")

        slot_2 = self.env['planning.slot'].create({
            'resource_id': self.resource_bert.id,
            'start_datetime': datetime.datetime(2020, 1, 6, 8, 0),
            'end_datetime': datetime.datetime(2020, 1, 7, 17, 0),
        })
        self.assertEqual(slot_2.leave_warning,
                         "bert is on time off from 01/06/2020 to 01/07/2020. \n")

        slot_3 = self.env['planning.slot'].create({
            'resource_id': self.resource_bert.id,
            'start_datetime': datetime.datetime(2020, 1, 6, 8, 0),
            'end_datetime': datetime.datetime(2020, 1, 10, 17, 0),
        })
        self.assertEqual(slot_3.leave_warning, "bert is on time off from 01/06/2020 to 01/10/2020. \n",
                         "should show the start of the 1st leave and end of the 2nd")

    def test_shift_update_according_time_off(self):
        """ working day and allocated hours of planning slot are update according to public holiday
        Test Case
        ---------
            1) Create slot
            2) Add public holiday
            3) Checked the allocated hour and working days count of slot
            4) Unlink the public holiday
            5) Checked the allocated hour and working days count of slot
        """
        with freeze_time("2020-04-10"):
            today = datetime.datetime.today()
            self.env.cr._now = today # used to force create_date, as sql is not wrapped by freeze gun

            ethan = self.env['hr.employee'].create({
                'create_date': today,
                'name': 'ethan',
                'tz': 'UTC',
                'employee_type': 'freelance',
            })

            slot = self.env['planning.slot'].create({
                'resource_id': ethan.resource_id.id,
                'employee_id': ethan.id,
                'start_datetime': datetime.datetime(2020, 4, 20, 8, 0), # Monday
                'end_datetime': datetime.datetime(2020, 4, 24, 17, 0),
            })

            initial_slot = {
                'allocated_hours': slot.allocated_hours,
            }

            # Add the public holiday
            public_holiday = self.env['resource.calendar.leaves'].create({
                'name': 'Public holiday',
                'calendar_id': ethan.resource_id.calendar_id.id,
                'date_from': datetime.datetime(2020, 4, 21, 8, 0), # Wednesday
                'date_to': datetime.datetime(2020, 4, 21, 17, 0),
            })

            self.assertNotEqual(slot.allocated_hours, initial_slot.get('allocated_hours'), 'Allocated hours should be updated')

            # Unlink the public holiday
            public_holiday.unlink()
            self.assertDictEqual(initial_slot, {
                'allocated_hours': slot.allocated_hours
                }, "The Working days and Allocated hours should be updated")

    def test_half_day_employee_leave(self):
        self.leave_type.request_unit = 'half_day'
        leave_1, leave_2 = self.env['hr.leave'].create([{
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': '2020-01-01 09:00:00',
            'request_date_to': '2020-01-01 13:00:00',
            'request_date_from_period': 'am',
            'request_date_to_period': 'am',
        }, {
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': '2020-01-02 14:00:00',
            'request_date_to': '2020-01-02 18:00:00',
            'request_date_from_period': 'pm',
            'request_date_to_period': 'pm',
        }])

        slot_1, slot_2 = self.env['planning.slot'].create([{
            'resource_id': self.resource_bert.id,
            'start_datetime': datetime.datetime(2020, 1, 1, 9, 0),
            'end_datetime': datetime.datetime(2020, 1, 1, 13, 0),
        }, {
            'resource_id': self.resource_bert.id,
            'start_datetime': datetime.datetime(2020, 1, 2, 14, 0),
            'end_datetime': datetime.datetime(2020, 1, 2, 18, 0),
        }])
        slot_3 = self.env['planning.slot'].create({
            'resource_id': self.resource_bert.id,
            'start_datetime': datetime.datetime(2020, 1, 3, 8, 0),
            'end_datetime': datetime.datetime(2020, 1, 3, 17, 0),
        })

        self.assertNotEqual(slot_1.leave_warning, False,
                             "Leave is not validated, but there is a warning for requested time off")
        self.assertNotEqual(slot_2.leave_warning, False,
                             "Leave is not validated, but there is a warning for requested time off")

        (leave_1 + leave_2).action_approve()

        self.assertNotEqual(slot_1.leave_warning, False,
                             "Employee is on leave, there should be a warning")
        self.assertNotEqual(slot_2.leave_warning, False,
                             "Employee is on leave, there should be a warning")
        self.assertEqual(
            re.sub(r'\s+', ' ', slot_1.leave_warning),
            "bert requested time off on 01/01/2020 from 9:00 AM to 1:00 PM. ",
        )
        self.assertEqual(
            re.sub(r'\s+', ' ', slot_2.leave_warning),
            "bert requested time off on 01/02/2020 from 2:00 PM to 6:00 PM. ",
        )
        self.assertEqual(slot_3.leave_warning, False,
                         "Employee is not on leave, there should be no warning")

    def test_progress_bar_with_holiday(self):
        """
        Test Case
        ---------
            1) Create one day time-off
            2) Create weekly shift
            3) Calculate percentage and verify
        """
        self.env['hr.leave'].sudo().create({
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': '2020-01-09',
            'request_date_to': '2020-01-09',
        }).action_approve()

        self.env['planning.slot'].sudo().create({
            'resource_id': self.resource_bert.id,
            'start_datetime': datetime.datetime(2020, 1, 7, 0, 0),
            'end_datetime': datetime.datetime(2020, 1, 10, 17, 0),
        })
        planning_hours_info = self.env['planning.slot']._gantt_progress_bar(
            'resource_id', self.resource_bert.ids, datetime.datetime(2020, 1, 5, 8, 0), datetime.datetime(2020, 1, 11, 17, 0)
        )
        self.assertEqual(75, (planning_hours_info[self.resource_bert.id]['value'] / planning_hours_info[self.resource_bert.id]['max_value']) * 100)

    def test_half_day_off_leave_of_flexible_resource(self):
        """
        Test half-day off leave for a flexible resource.
        The leave intervals should be set to 00:00:00 - 12:00:00 for AM half-day off
        and 12:00:00 - 23:59:59 for PM half-day off in the planning_gantt view.
        """
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flex Calendar',
            'tz': 'UTC',
            'flexible_hours': True,
            'hours_per_day': 8,
            'full_time_required_hours': 40,
            'attendance_ids': [],
        })
        employee = self.employee_bert
        employee.resource_calendar_id = flexible_calendar
        self.leave_type.request_unit = 'half_day'

        # Test AM half-day leave
        leave_am = self.env['hr.leave'].sudo().create({
            'name': 'AM Half Day Off',
            'employee_id': employee.id,
            'holiday_status_id': self.leave_type.id,
            'request_date_from': '2025-03-05',
            'request_date_to': '2025-03-05',
            'request_date_from_period': 'am',
            'request_date_to_period': 'am',
            'state': 'confirm',
        })
        leave_am.sudo().action_approve()

        start_dt_am = datetime.datetime(2025, 3, 5, 8, 0, 0, tzinfo=utc)
        end_dt_am = datetime.datetime(2025, 3, 5, 12, 0, 0, tzinfo=utc)

        intervals_am = flexible_calendar._leave_intervals_batch(start_dt_am, end_dt_am, [employee.resource_id])
        intervals_list_am = list(intervals_am[employee.resource_id.id])
        self.assertEqual(len(intervals_list_am), 1, "There should be one leave interval for AM half-day")
        interval_am = intervals_list_am[0]
        self.assertEqual(interval_am[0], start_dt_am, "The start of the interval should be 08:00:00")
        self.assertEqual(interval_am[1], end_dt_am, "The end of the interval should be 12:00:00")

        # Test PM half-day leave on next day
        leave_pm = self.env['hr.leave'].sudo().create({
            'name': 'PM Half Day Off',
            'employee_id': employee.id,
            'holiday_status_id': self.leave_type.id,
            'request_date_from': '2025-03-06',
            'request_date_to': '2025-03-06',
            'request_date_from_period': 'pm',
            'request_date_to_period': 'pm',
            'state': 'confirm',
        })
        leave_pm.sudo().action_approve()

        start_dt_pm = datetime.datetime(2025, 3, 6, 12, 0, 0, tzinfo=utc)
        end_dt_pm = datetime.datetime(2025, 3, 6, 16, 0, 0, 0, tzinfo=utc)

        intervals_pm = flexible_calendar._leave_intervals_batch(start_dt_pm, end_dt_pm, [employee.resource_id])
        intervals_list_pm = list(intervals_pm[employee.resource_id.id])
        self.assertEqual(len(intervals_list_pm), 1, "There should be one leave interval for PM half-day")
        interval_pm = intervals_list_pm[0]
        self.assertEqual(interval_pm[0], datetime.datetime(2025, 3, 6, 12, 0, 0, tzinfo=utc), "The start of the interval should be 12:00:00")
        self.assertEqual(interval_pm[1], end_dt_pm, "The end of the interval should be 16:00:00")

    def test_multiple_leaves_with_one_refusal_and_approval(self):
        """
        Test by creating 2 leaves for same date and same employee
        having a resource calendar of flexible hours with state of
        one refused and another approved.
        """
        self.employee_bert.resource_calendar_id = self.env['resource.calendar'].create({
            'name': 'Flex Calendar',
            'tz': 'UTC',
            'flexible_hours': True,
            'hours_per_day': 8,
            'full_time_required_hours': 40,
            'attendance_ids': [],
        })
        self.env['hr.leave'].sudo().create({
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': '2020-01-06',
            'request_date_to': '2020-01-07',
        }).action_refuse()
        self.env['hr.leave'].sudo().create({
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': '2020-01-06',
            'request_date_to': '2020-01-07',
        }).action_approve()

        slot_1 = self.env['planning.slot'].create({
            'resource_id': self.resource_bert.id,
            'start_datetime': datetime.datetime(2020, 1, 6, 8, 0),
            'end_datetime': datetime.datetime(2020, 1, 6, 17, 0),
        })

        self.assertEqual(slot_1.leave_warning,
                         "bert is on time off from 01/06/2020 to 01/07/2020. \n")

    def test_two_half_day_off_leaves_on_same_day_of_flexible_resource(self):
        """
        Test half-day off leave for a flexible resource.
        The leave intervals should be set to 08:00:00 - 16:00:00
        if 2 half-day offs on the same day(am and pm).
        """
        self.employee_bert.resource_calendar_id = self.flexible_calendar
        self.leave_type.request_unit = 'half_day'
        leave_am, leave_pm = self.env['hr.leave'].sudo().create([
            {
                'name': 'AM Half Day Off',
                'employee_id': self.employee_bert.id,
                'holiday_status_id': self.leave_type.id,
                'request_date_from': '2025-04-30',
                'request_date_to': '2025-04-30',
                'request_date_from_period': 'am',
                'request_date_to_period': 'am',
                'state': 'confirm',
            }, {
                'name': 'PM Half Day Off',
                'employee_id': self.employee_bert.id,
                'holiday_status_id': self.leave_type.id,
                'request_date_from': '2025-04-30',
                'request_date_to': '2025-04-30',
                'request_date_from_period': 'pm',
                'request_date_to_period': 'pm',
                'state': 'confirm',
            },
        ])
        leave_am.sudo().action_approve()
        leave_pm.sudo().action_approve()
        start_dt = datetime.datetime(2025, 4, 30, 0, 0, 0, tzinfo=utc)
        end_dt = datetime.datetime(2025, 4, 30, 23, 59, 59, 999999, tzinfo=utc)
        intervals = self.flexible_calendar._leave_intervals_batch(start_dt, end_dt, [self.employee_bert.resource_id])
        interval = next(iter(intervals[self.employee_bert.resource_id.id]))
        self.assertEqual(interval[0], datetime.datetime(2025, 4, 30, 8, 0, 0, tzinfo=utc), "The start of the interval should be 08:00:00")
        self.assertEqual(interval[1], datetime.datetime(2025, 4, 30, 16, 0, 0, tzinfo=utc), "The end of the interval should be 16:00:00")

    def test_batch_creation_from_calendar_with_time_off(self):
        """
        This test ensure that when planning slots are created from the "create multi" of the calendar view, the public
        holidays and time off are correctly computed.
        If some slots are supposed to be planned on public holidays/weekend, those slots are ignored.
        If some slots are supposed to be planned on a time off of a resource, those slots are ignored for the
        resource on time off, the other resource are correctly assigned to a new slot.
        """
        template = self.env['planning.slot.template'].create({
            'start_time': 9,
            'end_time': 13,
            'duration_days': 1,
        })
        ethan, chris = self.env['hr.employee'].create([{
            'create_date': datetime.datetime(2020, 4, 20, 8, 0),
            'name': 'ethan',
            'tz': 'UTC',
            'employee_type': 'freelance',
        }, {
            'create_date': datetime.datetime(2020, 4, 20, 8, 0),
            'name': 'Chris',
            'tz': 'UTC',
            'employee_type': 'freelance',
        }])

        # Public time off on Friday
        self.env['resource.calendar.leaves'].create({
            'name': 'Public holiday',
            'calendar_id': ethan.resource_id.calendar_id.id,
            'date_from': datetime.datetime(2025, 4, 4, 8, 0),
            'date_to': datetime.datetime(2025, 4, 4, 17, 0),
        })

        # Ethan is off on Thursday, Chris is off on Wednesday
        self.env['hr.leave'].sudo().create([
            {
                'holiday_status_id': self.leave_type.id,
                'employee_id': ethan.id,
                'request_date_from': '2025-4-3',
                'request_date_to': '2025-4-3',
            }, {
                'holiday_status_id': self.leave_type.id,
                'employee_id': chris.id,
                'request_date_from': '2025-4-2',
                'request_date_to': '2025-4-2',
            }
        ])._action_validate()

        # Only 2 new slots are expected :
        # - The slot on the 2nd April is a time off for chris
        # - The slot on the 3rd April is a time off for ethan
        # - The slot on the 4th April is a public holiday
        # - The 2 slots on the 5th April are set on a weekend
        slot_ethan, slot_chris = self.env['planning.slot'].create_batch_from_calendar(
            [{
                'start_datetime': f'2025-04-{day} 09:00:00', 'end_datetime': f'2025-04-{day} 13:00:00',
                'resource_id': employee.resource_id.id, 'template_id': template.id
            } for day in ('02', '03', '04', '05') for employee in (chris, ethan)]
        )

        self.assertEqual(slot_ethan.resource_id, ethan.resource_id)
        self.assertEqual(slot_ethan.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-02 09:00:00')
        self.assertEqual(slot_ethan.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-02 13:00:00')
        self.assertEqual(slot_chris.resource_id, chris.resource_id)
        self.assertEqual(slot_chris.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-03 09:00:00')
        self.assertEqual(slot_chris.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-03 13:00:00')

    def test_batch_creation_from_calendar_with_duration_days_template_and_time_off(self):
        """
        This test ensure that when planning slots are created from the "create multi" of the calendar view, the public
        holidays and time off are correctly computed.
        If some slots are supposed to be planned on public holidays/weekend, those slots are ignored.
        If some slots are supposed to be planned on a time off of a resource, those slots are ignored for the
        resource on time off, the other resource are correctly assigned to a new slot.
        """

        template = self.env['planning.slot.template'].create({
            'start_time': 8,
            'end_time': 12,
            'duration_days': 3,
        })
        ethan, chris = self.env['hr.employee'].create([{
            'create_date': datetime.datetime(2020, 4, 20, 8, 0),
            'name': 'ethan',
            'tz': 'UTC',
            'employee_type': 'freelance',
        }, {
            'create_date': datetime.datetime(2020, 4, 20, 8, 0),
            'name': 'Chris',
            'tz': 'UTC',
            'employee_type': 'freelance',
        }])

        # Wednesday is a public time off
        self.env['resource.calendar.leaves'].create({
            'name': 'Public holiday',
            'calendar_id': ethan.resource_id.calendar_id.id,
            'date_from': datetime.datetime(2025, 4, 2, 8, 0),
            'date_to': datetime.datetime(2025, 4, 2, 17, 0),
        })

        # Ethan is off on Thursday
        self.env['hr.leave'].sudo().create([
            {
                'holiday_status_id': self.leave_type.id,
                'employee_id': ethan.id,
                'request_date_from': '2025-4-3',
                'request_date_to': '2025-4-3',
            }
        ])._action_validate()

        # expected end date for Chris : 03 + 1 (public time off)
        # expected end date for Ethan : 03 + 4 (public time off + personal time off + weekend)
        slot_ethan, slot_chris = self.env['planning.slot'].create_batch_from_calendar(
            [{
                'start_datetime': '2025-04-01 08:00:00', 'end_datetime': '2025-04-03 12:00:00',
                'resource_id': employee.resource_id.id, 'template_id': template.id
            } for employee in (ethan, chris)]
        )

        self.assertEqual(slot_ethan.resource_id, ethan.resource_id)
        self.assertEqual(slot_ethan.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-01 08:00:00')
        self.assertEqual(slot_ethan.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-07 12:00:00')
        self.assertEqual(slot_chris.resource_id, chris.resource_id)
        self.assertEqual(slot_chris.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-01 08:00:00')
        self.assertEqual(slot_chris.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-04 12:00:00')

    def test_auto_plan_flexible_employee_with_holidays(self):
        self.env.user.tz = 'UTC'
        self.employee_bert.write({'resource_calendar_id': self.flexible_calendar.id, 'default_planning_role_id': self.flex_role.id})

        # date:            --------- 28/07 ---------|--------- 29/07 ---------|--------- 30/07 ----------|
        # schedule:        morning off |            |       |off(11->16)|     |            |afternoon off|
        # hours to work:              4H            |            3H           |           4H             |

        custom_leave, half_day_leave = self.env['hr.leave.type'].create([{
            'name': 'Custom Leave',
            'requires_allocation': False,
            'request_unit': 'hour',
        }, {
            'name': 'Half day',
            'requires_allocation': False,
            'request_unit': 'half_day',
        }])

        self.env['hr.leave'].with_context(mail_create_nolog=True, mail_notrack=True).create([{
            'name': 'Half 1',
            'holiday_status_id': half_day_leave.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': datetime.date(2025, 7, 28),
            'request_date_to': datetime.date(2025, 7, 28),
            'request_date_from_period': 'am',
            'request_date_to_period': 'am',
        }, {
            'name': 'Custom',
            'holiday_status_id': custom_leave.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': datetime.date(2025, 7, 29),
            'request_date_to': datetime.date(2025, 7, 29),
            'request_hour_from': 11.0,
            'request_hour_to': 16.0,
        }, {
            'name': 'Half 2',
            'holiday_status_id': half_day_leave.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': datetime.date(2025, 7, 30),
            'request_date_to': datetime.date(2025, 7, 30),
            'request_date_from_period': 'pm',
            'request_date_to_period': 'pm',
        }]).action_approve()

        shift = self.env['planning.slot'].create({
            'name': 'Night Shift',
            'start_datetime': datetime.datetime(2025, 7, 28, 8),
            'end_datetime': datetime.datetime(2025, 7, 30, 16),
            'role_id': self.flex_role.id,
        })
        shift.allocated_hours = 5.5

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2025-07-26 22:00:00",
            default_end_datetime="2025-08-01 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2025-08-01 22:00:00'], ['end_datetime', '>', '2025-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [shift.id])
        self.assertEqual(shift.resource_id.employee_id, self.employee_bert)
        self.assertEqual(shift.allocated_percentage, 50.0, "allocated_hours = 5.5 / hours to work = 11")

        shift2 = self.env['planning.slot'].create({
            'name': 'Night Shift',
            'start_datetime': datetime.datetime(2025, 7, 28, 8),
            'end_datetime': datetime.datetime(2025, 7, 30, 16, 0),
            'role_id': self.flex_role.id,
            'allocated_hours': 5.5,
        })

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2025-07-26 22:00:00",
            default_end_datetime="2025-08-01 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2025-08-01 22:00:00'], ['end_datetime', '>', '2025-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [shift2.id])
        self.assertEqual(shift2.resource_id.employee_id, self.employee_bert)
        self.assertEqual(shift2.allocated_percentage, 50.0, "allocated_hours = 5.5 / hours to work 11")

        shift3 = self.env['planning.slot'].create({
            'name': 'Night Shift',
            'start_datetime': datetime.datetime(2025, 7, 28, 8),
            'end_datetime': datetime.datetime(2025, 7, 30, 16, 0),
            'role_id': self.flex_role.id,
            'allocated_hours': 1,
        })

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2025-07-26 22:00:00",
            default_end_datetime="2025-08-01 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2025-08-01 22:00:00'], ['end_datetime', '>', '2025-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [], "max hours already done 5.5 + 5.5 = 11")
        self.assertFalse(shift3.resource_id.employee_id)
