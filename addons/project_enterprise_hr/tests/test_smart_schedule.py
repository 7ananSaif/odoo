# Part of Odoo. See LICENSE file for full copyright and licensing details

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from markupsafe import Markup
import pytz
from odoo.tests import tagged, freeze_time
from odoo.tools import float_compare
from odoo.addons.project_enterprise.tests.test_smart_schedule_common import TestSmartScheduleCommon
from .auto_shift_dates_hr_common import AutoShiftDatesHRCommon


@tagged('-at_install', 'post_install')
@freeze_time('2023-01-01')
class TestSmartSchedule(TestSmartScheduleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.flexible_calendar = cls.env['resource.calendar'].create({
            'name': 'Flex Calendar 8h',
            'tz': 'UTC',
            'full_time_required_hours': 40.0,
            'hours_per_day': 8.0,
            'flexible_hours': True,
        })

    def test_multi_users_tasks(self):
        """
            user_projectuser     [task_project_pigs_with_allocated_hours_user] [task_project_goats_with_allocated_hours_user]                                               [task_project_pigs_no_allocated_hours_user]
                                                                            |                                                                                                ^
                                                                            |                                                                                                |
                                                                            |                                                                                                |
            user_projectmanager                                             ------------------------------------------------>[task_project_pigs_with_allocated_hours_manager]-
            and user_projectuser
        """
        self.task_project_pigs_with_allocated_hours_manager.write({
            "user_ids": [self.user_projectmanager.id, self.user_projectuser.id],
            "depend_on_ids": [self.task_project_pigs_with_allocated_hours_user.id],
            "dependent_ids": [self.task_project_pigs_no_allocated_hours_user.id],
            "date_deadline": datetime(2023, 2, 2),
            "allocated_hours": 10.0,  # allocated hours should be equal remaining hours when timesheet_grid installed to have some hours to plan ( for testing simplicity )
        })

        self.task_project_pigs_no_allocated_hours_user.write({
            "user_ids": [self.user_projectuser.id],
        })

        self.env["hr.employee"].create([{
            "name": self.user_projectuser.name,
            "user_id": self.user_projectuser.id
        }, {
            "name": self.user_projectmanager.name,
            "user_id": self.user_projectmanager.id
        }])

        self.env['resource.calendar.leaves'].create([{
            'name': 'scheduled leave',
            'date_from': datetime(2023, 1, 3, 0),
            'date_to': datetime(2023, 1, 6, 23),
            'resource_id': self.user_projectuser.employee_id.resource_id.id,
            'time_type': 'leave',
        }, {
            'name': 'scheduled leave',
            'date_from': datetime(2023, 1, 5, 0),
            'date_to': datetime(2023, 1, 10, 23),
            'resource_id': self.user_projectmanager.employee_id.resource_id.id,
            'time_type': 'leave',
        }])

        result = (
            self.task_project_pigs_with_allocated_hours_user + self.task_project_pigs_with_allocated_hours_manager + self.task_project_pigs_no_allocated_hours_user + self.task_project_goats_with_allocated_hours_user
        ).with_context({
            'last_date_view': self.end_date_view_str,
            'gantt_scale': "week",
            'cell_part': 2.0,
        }).schedule_tasks({
            'planned_date_begin': self.start_date_view_str,
            'date_deadline': (self.start_date_view + relativedelta(day=1)).strftime('%Y-%m-%d %H:%M:%S'),
            'user_ids': self.user_projectuser.ids,
        })
        # Test no warning is displayed
        self.assertDictEqual(result[0], {}, 'No warnings should be displayed')

        self.assertEqual(self.task_project_pigs_with_allocated_hours_user.planned_date_begin, datetime(2023, 1, 2, 7))
        self.assertEqual(self.task_project_pigs_with_allocated_hours_user.date_deadline, datetime(2023, 1, 2, 16))

        # user_projectuser is off till 6
        # user_projectmanager is off till 10
        # the first possible time for both of them is starting from 11
        self.assertEqual(self.task_project_pigs_with_allocated_hours_manager.planned_date_begin, datetime(2023, 1, 11, 7))
        self.assertEqual(self.task_project_pigs_with_allocated_hours_manager.date_deadline, datetime(2023, 1, 11, 13), "10 hours to do / 2 users = 5 hours per user from 7h to 11h + 12h to 13h")

        # even that task_project_pigs_with_allocated_hours_manager was planned first as it has a deadline
        # smart scheduling is optimizing resources so
        # the gap in days 09 and 10 was filled to plan task_project_goats_with_allocated_hours_user
        self.assertEqual(self.task_project_goats_with_allocated_hours_user.planned_date_begin, datetime(2023, 1, 9, 7))
        self.assertEqual(self.task_project_goats_with_allocated_hours_user.date_deadline, datetime(2023, 1, 10, 9))

        # should not be planned after the old deadline of its parent, as its parent will be planned again
        # if the new deadline is before the old one, no need to block the task and plan it ASAP
        self.assertEqual(self.task_project_pigs_no_allocated_hours_user.planned_date_begin, datetime(2023, 1, 11, 13))
        self.assertEqual(self.task_project_pigs_no_allocated_hours_user.date_deadline, datetime(2023, 1, 13, 8), "12h to plan, 3 hours day 11, 8 hours day 12, 1 hour day 13")

    def test_auto_schedule_flex_resource(self):
        """
        user_projectuser(flex)    [task_project_pigs_with_allocated_hours_user] ----> [task_project_goats_with_allocated_hours_user]                                                   [task_project_pigs_no_allocated_hours_no_user]
                                                                                                          |                                                                              ^
        both users (flex and regular)                                                                     |----------------------------> [task_project_pigs_no_allocated_hours_user]------
        """
        self.env.user.sudo().tz = 'UTC'
        self.user_projectuser.company_id.resource_calendar_id.tz = 'UTC'

        self.task_project_pigs_with_allocated_hours_user.allocated_hours = 36
        self.user_projectuser.action_create_employee()
        self.user_projectmanager.action_create_employee()
        self.user_projectuser.employee_id.write({"resource_calendar_id": self.flexible_calendar.id})
        (self.user_projectuser.employee_id.resource_id | self.user_projectmanager.employee_id.resource_id).write({'tz': 'UTC'})

        self.task_project_goats_with_allocated_hours_user.write({
            "user_ids": [self.user_projectuser.id],
            "depend_on_ids": [self.task_project_pigs_with_allocated_hours_user.id],
            "dependent_ids": [self.task_project_pigs_no_allocated_hours_user.id],
            "allocated_hours": 12,
        })

        self.task_project_pigs_no_allocated_hours_no_user.write({"user_ids": [self.user_projectuser.id], "allocated_hours": 12})
        self.task_project_pigs_no_allocated_hours_user.write({
            "user_ids": [self.user_projectuser.id, self.user_projectmanager.id],
            "dependent_ids": [self.task_project_pigs_no_allocated_hours_no_user.id],
            "allocated_hours": 8,
        })

        result = (
            self.task_project_pigs_with_allocated_hours_user | self.task_project_goats_with_allocated_hours_user | self.task_project_pigs_no_allocated_hours_user | self.task_project_pigs_no_allocated_hours_no_user
        ).with_context({
            'last_date_view': self.end_date_view_str,
            'gantt_scale': "week",
            'cell_part': 2.0,
        }).schedule_tasks({
            'planned_date_begin': self.start_date_view_str,
            'date_deadline': (self.start_date_view + relativedelta(day=1)).strftime('%Y-%m-%d %H:%M:%S'),
            'user_ids': self.user_projectuser.ids,
        })
        self.assertDictEqual(result[0], {}, 'No warnings should be displayed')

        self.assertEqual(self.task_project_pigs_with_allocated_hours_user.planned_date_begin, datetime(2023, 1, 1, 0), "day 1: 8h, day 2: 8h, day 3: 8h, day 4: 8h, day 5: 4h")
        self.assertEqual(self.task_project_pigs_with_allocated_hours_user.date_deadline, datetime(2023, 1, 5, 4), "4 hours left to work on other tasks")

        self.assertEqual(self.task_project_goats_with_allocated_hours_user.planned_date_begin, datetime(2023, 1, 5, 4), "4 hours to work from 04:00 to 08:00")
        self.assertEqual(self.task_project_goats_with_allocated_hours_user.date_deadline, datetime(2023, 1, 8, 8), "40 hours already done on week 1, day 6 and 7 should be off, 8 hours done on day 8 from 00:00 to 08:00")

        self.assertEqual(self.task_project_pigs_no_allocated_hours_user.planned_date_begin, datetime(2023, 1, 9, 8), "8 hours to do, 4 hours each user on day 9 from 08:00 to 12:00 (start from 08:00 instead of 00:00 as a regular resource is part of it)")
        self.assertEqual(self.task_project_pigs_no_allocated_hours_user.date_deadline, datetime(2023, 1, 9, 12))

        self.assertEqual(self.task_project_pigs_no_allocated_hours_no_user.planned_date_begin, datetime(2023, 1, 9, 12), "4 hours on day 9")
        self.assertEqual(self.task_project_pigs_no_allocated_hours_no_user.date_deadline, datetime(2023, 1, 10, 8), "8 hours on day 10")

    def test_flexible_user_no_day_no_week_overload(self):
        """
            task1:
                - total duration   56 hours
                - allocated hours  24 hours

                Repartition:
                    * day 28:
                        16 / 56 hours with a rate ~ 28.5%
                        2 employees work 24(allocated_hours) * rate = 6.85 hours - an employee works 3.42 hours

                    * day 29:
                        24 / 56 hours with a rate ~ 43%
                        2 employees work 24(allocated_hours) * 10.28 hours - an employee works 5.14 hours

                    * day 30:
                        16 / 56 hours with a rate ~ 28.5%
                        2 employees work 24(allocated_hours) * 6.85 hours - an employee works 3.42 hours

            task 2
                - total duration   12 hours ctd bx
                - allocated hours   6 hours

                Repartition:
                    * day 28:
                        2 / 12 hours  with a rate ~ 16%
                        an employee works ~ 1 hour

                    * day 29:
                        10 / 12 hours with a rate ~ 83%
                        an employee works ~ 5 hours

            user_projectuser works:
                - day 28: ~ 4.42 hours
                - day 29: ~ 10.14 hours (overloaded)
                - day 30: ~ 3.42
        """
        self.env.user.sudo().tz = 'UTC'
        self.user_projectuser.company_id.resource_calendar_id.tz = 'UTC'

        self.user_projectuser.action_create_employee()
        self.user_projectmanager.action_create_employee()
        self.user_projectuser.employee_id.write({"resource_calendar_id": self.flexible_calendar.id, "tz": "UTC"})
        (self.user_projectuser.employee_id.resource_id | self.user_projectmanager.employee_id.resource_id).write({'tz': 'UTC'})

        self.task_project_goats_with_allocated_hours_user.write({
            "user_ids": [self.user_projectuser.id, self.user_projectmanager.id],
            "planned_date_begin": datetime(2023, 7, 28, 8),
            "date_deadline": datetime(2023, 7, 30, 16),
            "allocated_hours": 24,
        })

        self.task_project_pigs_with_allocated_hours_user.write({
            "user_ids": [self.user_projectuser.id],
            "planned_date_begin": datetime(2023, 7, 28, 22),
            "date_deadline": datetime(2023, 7, 29, 10),
            "allocated_hours": 6,
        })

        min_start, max_end = pytz.utc.localize(datetime(2023, 7, 28)), pytz.utc.localize(datetime(2023, 7, 30, 16))
        _dummy, flex_users_hours_per_day, flex_user_work_hours_per_week = self.task_project_pigs_no_allocated_hours_user._web_gantt_get_valid_intervals(min_start, max_end, self.user_projectuser | self.user_projectmanager)

        self.assertEqual(float_compare(flex_users_hours_per_day[self.user_projectuser.id][date(2023, 7, 28)], 3.57, precision_digits=2), 0, "8 - 4.42")
        self.assertEqual(float_compare(flex_users_hours_per_day[self.user_projectuser.id][date(2023, 7, 29)], -2.14, precision_digits=2), 0, "8 - 10.14")
        self.assertEqual(float_compare(flex_users_hours_per_day[self.user_projectuser.id][date(2023, 7, 30)], 4.57, precision_digits=2), 0, "8 - 3.42")
        self.assertTrue(self.user_projectmanager.id not in flex_users_hours_per_day, "only users with flexible resources")
        self.assertEqual(self.task_project_pigs_with_allocated_hours_user.planning_overlap, Markup('<p>Armande ProjectUser has 1 tasks at the same time.</p>'))

        self.assertEqual(float_compare(flex_user_work_hours_per_week[self.user_projectuser.id][2023, 30], 25.43, precision_digits=2), 0, "day 28, 29 belong to week 30, 40 - (4.42 + 10.14) = 25.428 ~ 25.43")
        self.assertEqual(float_compare(flex_user_work_hours_per_week[self.user_projectuser.id][2023, 31], 36.57, precision_digits=2), 0, "day 30 belings to week 31 (40 - 3.42) = 36.57")
        self.assertTrue(self.user_projectmanager.id not in flex_user_work_hours_per_week, "only users with flexible resources")

        # auto plan tasks in a period with already planned tasks
        self.task_project_pigs_no_allocated_hours_no_user.write({"user_ids": [self.user_projectuser.id], "allocated_hours": 12})
        self.task_project_pigs_no_allocated_hours_user.write({"user_ids": [self.user_projectuser.id, self.user_projectmanager.id], "allocated_hours": 12})

        result = (
            self.task_project_pigs_no_allocated_hours_no_user | self.task_project_pigs_no_allocated_hours_user
        ).with_context({
            'last_date_view': (min_start + relativedelta(months=1)).strftime('%Y-%m-%d %H:%M:%S'),
            'gantt_scale': "week",
            'cell_part': 2.0,
        }).schedule_tasks({
            'planned_date_begin': min_start.strftime('%Y-%m-%d %H:%M:%S'),
            'date_deadline': (min_start + relativedelta(day=1)).strftime('%Y-%m-%d %H:%M:%S'),
        })

        self.assertDictEqual(result[0], {}, 'No warnings should be displayed')

        self.assertEqual(self.task_project_pigs_no_allocated_hours_no_user.planned_date_begin, datetime(2023, 7, 28, 0))
        self.assertEqual(self.task_project_pigs_no_allocated_hours_no_user.date_deadline, datetime(2023, 7, 31, 3, 51, 25, 714285), """
            allocated hours = 12 planned:
                - 3.57 hours: datetime(2023, 7, 28, 0, 0) -> datetime(2023, 7, 28, 3, 34, 17, 142858)
                - 0 hours: day 29, already overloaded
                - 4.57 hours: datetime(2023, 7, 30, 16, 0 -> datetime(2023, 7, 30, 20, 34, 17, 142857)
                - 3.87 hours: datetime(2023, 7, 31, 0, 0) -> datetime(2023, 7, 31, 3, 51, 25, 714285)
            """
        )

        self.assertEqual(self.task_project_pigs_no_allocated_hours_user.planned_date_begin, datetime(2023, 7, 31, 8))
        self.assertEqual(self.task_project_pigs_no_allocated_hours_user.date_deadline, datetime(2023, 8, 1, 9, 51, 25, 714285), """
            allocated hours = 12 planned and assigned to 2 users (only one is flex, attendances should be the intersection), each user have 6 hours to do:
                - 4 hours: 31 morning - datetime(2023, 7, 31, 8) -> datetime(2023, 7, 31, 12)
                - ~0.13 hours = (8 - 3.87 - 4) =~ 8 minutes: datetime(2023, 7, 31, 13) -> datetime(2023, 7, 31, 13, 8, 34, 285715)
                - 1.87 hours: datetime(2023, 8, 1, 8, 0) -> datetime(2023, 8, 1, 9, 51, 25, 714285)
            """
        )

        self.task_project_pigs_with_allocated_hours_user.allocated_hours = 0
        self.assertFalse(self.task_project_pigs_with_allocated_hours_user.planning_overlap, "24 hours done in 3 days, no overload")

    def test_auto_schedule_fully_flex_resource(self):
        """
        user_projectuser(flex)    [task_project_pigs_with_allocated_hours_user] ----> [task_project_goats_with_allocated_hours_user]                                                   [task_project_pigs_no_allocated_hours_no_user]
                                                                                                          |                                                                              ^
        both users (flex and regular)                                                                     |----------------------------> [task_project_pigs_no_allocated_hours_user]------
        """
        self.env.user.sudo().tz = 'UTC'
        self.user_projectuser.company_id.resource_calendar_id.tz = 'UTC'

        self.task_project_pigs_with_allocated_hours_user.allocated_hours = 36
        self.user_projectuser.action_create_employee()
        self.user_projectmanager.action_create_employee()
        self.user_projectuser.employee_id.write({"resource_calendar_id": False})
        (self.user_projectuser.employee_id.resource_id | self.user_projectmanager.employee_id.resource_id).write({'tz': 'UTC'})

        self.task_project_goats_with_allocated_hours_user.write({
            "user_ids": [self.user_projectuser.id],
            "depend_on_ids": [self.task_project_pigs_with_allocated_hours_user.id],
            "dependent_ids": [self.task_project_pigs_no_allocated_hours_user.id],
            "allocated_hours": 12,
        })

        self.task_project_pigs_no_allocated_hours_no_user.write({"user_ids": [self.user_projectuser.id], "allocated_hours": 12})
        self.task_project_pigs_no_allocated_hours_user.write({
            "user_ids": [self.user_projectuser.id, self.user_projectmanager.id],
            "dependent_ids": [self.task_project_pigs_no_allocated_hours_no_user.id],
            "allocated_hours": 8,
        })

        result = (
            self.task_project_pigs_with_allocated_hours_user | self.task_project_goats_with_allocated_hours_user | self.task_project_pigs_no_allocated_hours_user | self.task_project_pigs_no_allocated_hours_no_user
        ).with_context({
            'last_date_view': self.end_date_view_str,
            'gantt_scale': "week",
            'cell_part': 2.0,
        }).schedule_tasks({
            'planned_date_begin': self.start_date_view_str,
            'date_deadline': (self.start_date_view + relativedelta(day=1)).strftime('%Y-%m-%d %H:%M:%S'),
            'user_ids': self.user_projectuser.ids,
        })
        self.assertDictEqual(result[0], {}, 'No warnings should be displayed')

        self.assertEqual(self.task_project_pigs_with_allocated_hours_user.planned_date_begin, datetime(2023, 1, 1, 0), "day 1: 24h, no daily limit")
        self.assertEqual(self.task_project_pigs_with_allocated_hours_user.date_deadline, datetime(2023, 1, 2, 12), "day 2: 12h, no daily limit")

        self.assertEqual(self.task_project_goats_with_allocated_hours_user.planned_date_begin, datetime(2023, 1, 2, 12), "day 2, 12 hours, no daily limit")
        self.assertEqual(self.task_project_goats_with_allocated_hours_user.date_deadline, datetime(2023, 1, 3, 0))

        self.assertEqual(self.task_project_pigs_no_allocated_hours_user.planned_date_begin, datetime(2023, 1, 3, 8), "8 hours to do, 4 hours each user on day 9 from 08:00 to 12:00 (start from 08:00 instead of 00:00 as a regular resource is part of it)")
        self.assertEqual(self.task_project_pigs_no_allocated_hours_user.date_deadline, datetime(2023, 1, 3, 12))

        self.assertEqual(self.task_project_pigs_no_allocated_hours_no_user.planned_date_begin, datetime(2023, 1, 3, 12), "12 hours on day 3")
        self.assertEqual(self.task_project_pigs_no_allocated_hours_no_user.date_deadline, datetime(2023, 1, 4, 0))


class ProjectEnterpriseHrTestSmartScheduleWithVersion(AutoShiftDatesHRCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.armande_employee.version_id.write({
            'date_version': datetime(2023, 1, 1),
            'contract_date_start': datetime(2023, 1, 1),
            'contract_date_end': datetime(2023, 8, 10),
            'name': 'CDD Contract for Armande ProjectUser',
            'resource_calendar_id': cls.calendar_morning.id,
            'wage': 5000.0,
        })
        cls.contract = cls.armande_employee.version_id

    def test_auto_plan_with_expired_contract(self):
        self.task_1.write({
            "planned_date_begin": False,
            "date_deadline": False,
        })

        res = self.task_1.with_context({
            'last_date_view': '2023-10-31 22:00:00',
            'cell_part': 2.0,
        }).schedule_tasks({
            'planned_date_begin': '2023-08-15 22:00:00',
            'date_deadline': '2023-10-16 21:59:59',
            'user_ids': self.armande_employee.user_id.ids,
        })

        self.assertEqual(next(iter(res[0].keys())), 'no_intervals')
        self.assertEqual(res[1], {}, "no pills planned")
        self.assertFalse(self.task_1.planned_date_begin)
        self.assertFalse(self.task_1.date_deadline)
