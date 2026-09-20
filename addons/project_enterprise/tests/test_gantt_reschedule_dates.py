# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo.fields import Command
from odoo.tests.common import users, tagged, freeze_time
from .gantt_reschedule_dates_common import ProjectEnterpriseGanttRescheduleCommon, fake_now


@tagged('gantt_reschedule', 'post_install', '-at_install')
@freeze_time(fake_now)
class TestGanttRescheduleOnTasks(ProjectEnterpriseGanttRescheduleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.task_1_date_deadline -= timedelta(hours=2)
        cls.task_1.write({"date_deadline": cls.task_1_date_deadline, "allocated_hours": 1})

    def test_gantt_reschedule_date_not_active(self):
        """ This test purpose is to ensure that auto shift date feature is not active when it shouldn't:
            * When the task has no project (either the moved task or the linked one (depend_on_ids or dependent_ids).
            * When the calculated planned_start_date is prior to now.
        """

        def test_task_3_dates_unchanged(task_1_new_planned_dates, failed_message, domain_force=False, **context):
            task_1 = self.task_1.with_context(context) if domain_force else self.task_1.with_context(**context)
            self.gantt_reschedule_consume_buffer(self.task_1, task_1_new_planned_dates)
            self.assertEqual(self.task_3_planned_date_begin, self.task_3.planned_date_begin, failed_message)
            self.assertEqual(self.task_3_date_deadline, self.task_3.date_deadline, failed_message)
            task_1.write({
                'planned_date_begin': self.task_1_planned_date_begin,
                'date_deadline': self.task_1_date_deadline,
            })

        self.task_4.depend_on_ids = [Command.clear()]

        # Checks that no date shift is made when the moved task has no project_id
        failed_message = "The auto shift date feature should not be triggered after having moved a task that " \
                         "does not have a project_id."
        project_id = self.task_1.project_id
        self.task_1.write({
            'project_id': False
        })
        test_task_3_dates_unchanged(self.task_1_date_gantt_reschedule_trigger(), failed_message)
        self.task_1.write({
            'project_id': project_id.id
        })

        # Checks that no date shift is made when the linked task has no project_id
        failed_message = "The auto shift date feature should not be triggered on tasks (depend_on_ids/dependent_ids) " \
                         "that do have a project_id."
        project_id = self.task_3.project_id
        self.task_3.write({
            'project_id': False
        })
        test_task_3_dates_unchanged(self.task_1_date_gantt_reschedule_trigger(), failed_message)
        self.task_3.write({
            'project_id': project_id.id
        })

        # Checks that no date shift is made when the new planned_date is prior to the current datetime.
        with freeze_time(self.task_1_no_date_gantt_reschedule_trigger()['planned_date_begin'] + relativedelta(weeks=1)):
            failed_message = "The auto shift date feature should not trigger any changes when the new planned_date " \
                             "is prior to the current datetime."
            test_task_3_dates_unchanged(self.task_1_date_gantt_reschedule_trigger(), failed_message)

    def test_gantt_reschedule_forward_dependent_task_consume_and_maintain_buffer(self):
        """
            All tasks in this test have allocated_hours, so their duration is computed according to the allocated hours
            Initial state:
                            ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
                            │ Task 1  │ -->  │ Task 3  │ -->  │ Task 4  │ -->  │ Task 5  │ -->  │ Task 6  │
                            │         │      │         │      │         │      │02/08 8H │      │         │
                            │ 24/06   │      │ 24/06   │      │ 30/06   │      │   ->    │      │ 04/08   │
                            │ 9H > 10H│      │13H > 15H│      │15H > 17H│      │03/08 17H│      │ 8H->17H │
                            └─────────┘      └─────────┘      └─────────┘      └─────────┘      └─────────┘

            buffer(1, 3) = 2 hours (10H -> 12H), lunch hour from 12H -> 13H is not counted
            buffer(3, 4) = 32 hours
            buffer(4, 5) = 0
            buffer(5, 6) = 0

        This test purpose is to ensure that task 3 that depends on a task 1 is shifted forward when task 1 advances in 2 ways:
            1- consume buffer: task 3 can start directly (when possible) after task 1, tasks 4, 5, 6 should not be replanned as there no
        conflicts to solve.

            2- maintain buffer: task 3 should start after min = buffer = 2H after the end of task 1, tasks 4, 5 and 6 should move as the buffer should
        be maintained

                             ┌─────────┐
                             │ Task 1  │
                             │         │
                             │ 24/06   │
                             │13H > 14H│
                             └─────────┘
                                   |
                                   |  ┌─────────┐
                                   |  │ Task 3  │
                                   -->│         │   task 3 should move to the right with its children 4, 5 and 6
                                      │ 24/06   │             =>
                                      │13H > 15H│
                                      └─────────┘
        """

        moved_tasks = self.task_3 | self.task_1
        not_moved_tasks = self.task_4 | self.task_5 | self.task_6
        old_vals = {
            task.name: (task.planned_date_begin, task.date_deadline)
            for task in moved_tasks
        }

        # 1- consume buffer
        res = self.gantt_reschedule_consume_buffer(self.task_1, self.task_1_date_gantt_reschedule_trigger())
        self.assert_old_tasks_vals(res, 'success', 'Tasks rescheduled', moved_tasks, old_vals)

        failed_message = "The auto shift date feature should move forward a dependent tasks."
        self.assertEqual(self.task_3.planned_date_begin, datetime(2021, 6, 24, 14), failed_message)
        self.assertEqual(self.task_3.date_deadline, datetime(2021, 6, 24, 16), failed_message)
        self.assertEqual(self.task_1.planned_date_begin, datetime(2021, 6, 24, 13), failed_message)
        self.assertEqual(self.task_1.date_deadline, datetime(2021, 6, 24, 14), failed_message)
        self.assert_task_not_replanned(not_moved_tasks, self.project_pigs_intial_dates())

        moved_tasks.action_rollback_scheduling(res['old_vals_per_pill_id'])
        self.assertEqual((self.task_3.planned_date_begin, self.task_3.date_deadline), old_vals[self.task_3.name])
        self.assertEqual((self.task_1.planned_date_begin, self.task_1.date_deadline), old_vals[self.task_1.name])

        # 2- maintain buffer
        moved_tasks |= not_moved_tasks
        for task in not_moved_tasks:
            old_vals[task.name] = (task.planned_date_begin, task.date_deadline)

        res = self.gantt_reschedule_maintain_buffer(self.task_1, self.task_1_date_gantt_reschedule_trigger())
        self.assert_old_tasks_vals(res, 'success', 'Tasks rescheduled', moved_tasks, old_vals)

        self.assertEqual(self.task_1.planned_date_begin, datetime(2021, 6, 24, 13), failed_message)
        self.assertEqual(self.task_1.date_deadline, datetime(2021, 6, 24, 14), failed_message)
        self.assertEqual(self.task_3.planned_date_begin, datetime(2021, 6, 24, 16), failed_message + "tasks 3 should start after buffer = 2 hours after the end of task 1")
        self.assertEqual(self.task_3.date_deadline, datetime(2021, 6, 25, 9), failed_message + "tasks 3 should start after buffer = 2 hours after the end of task 1")

        self.assertEqual(self.task_4.planned_date_begin, datetime(2021, 8, 2, 9), failed_message + """
            buffer between task 3 and 4 = 32H
            we need to wait 31h in month 6 (7 hours on day 25 and 24 Hours on the last week)
            month 7 is off for the company
            1 hours on monday 02/08
        """)
        self.assertEqual(self.task_4.date_deadline, self.task_5.planned_date_begin, failed_message + "buffer = 0 between task 4 and 5 as month 07 was off")
        self.assertEqual(self.task_5.date_deadline, self.task_6.planned_date_begin, failed_message + "buffer = 0 between task 5 and 6")

    def test_gantt_reschedule_backward_dependent_task_consume_and_maintain_buffer(self):
        """
            All tasks in this test have allocated_hours, so their duration is computed according to the allocated hours
            This test purpose is to ensure that a task A that depends on a task B is shifted backward, up to before
                B planned_date_start field value.

                                        ┌─────────┐
            task 5 should move          │ Task 5  │
            to the left with            | 02/08 8H|
            its ancestors               │  ->     │
                    <=                  │         │-------
                                        │03/08 17H│      |
                                        └─────────┘      |
                                       |------------------
                                       |  ┌─────────┐
                                       |  │ Task 6  │
                                       -->│         │
                                          │ 03/08   │
                                          │08H > 17H│
                                          └─────────┘
        """
        moved_tasks = self.task_6 | self.task_5 | self.task_4
        not_moved_tasks = self.task_3 | self.task_1
        old_vals = {
            task.name: (task.planned_date_begin, task.date_deadline)
            for task in moved_tasks
        }

        task_6_vals = {
            "planned_date_begin": '2021-08-03 08:00:00',
            "date_deadline": '2021-08-03 17:00:00'
        }

        # 1- consume buffer
        res = self.gantt_reschedule_consume_buffer(self.task_6, task_6_vals)
        self.assert_old_tasks_vals(res, 'success', 'Tasks rescheduled', moved_tasks, old_vals)

        failed_message = "The auto shift date feature should move forward a dependent tasks."
        self.assertEqual(self.task_6.planned_date_begin, datetime(2021, 8, 3, 8), failed_message)
        self.assertEqual(self.task_6.date_deadline, datetime(2021, 8, 3, 17), failed_message)
        self.assertEqual(self.task_5.planned_date_begin, datetime(2021, 6, 30, 8), failed_message)
        self.assertEqual(self.task_5.date_deadline, datetime(2021, 8, 2, 17), failed_message)
        self.assert_task_not_replanned(not_moved_tasks, self.project_pigs_intial_dates())

        moved_tasks.action_rollback_scheduling(res['old_vals_per_pill_id'])
        for task in moved_tasks:
            self.assertEqual((task.planned_date_begin, task.date_deadline), old_vals[task.name])

        """
            2- maintain buffer

            buffer(5, 6) = 0
            buffer(4, 5) = 0
            buffer(4, 3) = 32H => as task 4 were moved day in the past, task 3 moved also 1 day in the past to keep the buffer
            buffer(1, 3) = 2H => task 1 will also follow by moving one day in the past to keep the buffer

            INFO: it's one day in the back by chance because it's still in a valid period (task 5 and task 6 are counter examples)

            ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
            │ Task 1  │ -->  │ Task 3  │ -->  │ Task 4  │ -->  │ Task 5  │ -->  │ Task 6  │
            │         │      │         │      │         │      │30/06 8H │      │         │
            │ 23/06   │      │ 23/06   │      │ 29/06   │      │   ->    │      │ 03/08   │
            │ 9H > 10H│      │13H > 15H│      │15H > 17H│      │02/08 17H│      │ 8H->17H │
            └─────────┘      └─────────┘      └─────────┘      └─────────┘      └─────────┘
        """
        moved_tasks |= not_moved_tasks
        for task in not_moved_tasks:
            old_vals[task.name] = (task.planned_date_begin, task.date_deadline)

        res = self.gantt_reschedule_maintain_buffer(self.task_6, task_6_vals)
        self.assert_old_tasks_vals(res, 'success', 'Tasks rescheduled', moved_tasks, old_vals)

        self.assertEqual(self.task_6.planned_date_begin, datetime(2021, 8, 3, 8), failed_message)
        self.assertEqual(self.task_6.date_deadline, datetime(2021, 8, 3, 17), failed_message)
        self.assertEqual(self.task_5.planned_date_begin, datetime(2021, 6, 30, 8), failed_message)
        self.assertEqual(self.task_5.date_deadline, datetime(2021, 8, 2, 17), failed_message + "buffer = 0 between task 5 and 6, and month 07 is off")

        for task in self.task_1 | self.task_3 | self.task_4:
            self.assertEqual(task.planned_date_begin, old_vals[task.name][0] + timedelta(days=-1), failed_message)
            self.assertEqual(task.date_deadline, old_vals[task.name][1] + timedelta(days=-1), failed_message)

    def test_gantt_reschedule_forward_dependent_task_maintain_buffer_with_missing_start_date_on_task(self):
        """
            Tests forward rescheduling with maintain buffer when a dependent task (Task 3) has no planned start date.
            Task 1 move to the right, but Task 3 and its children 4, 5 and 6 remains unchanged due to Task 3
            missing planned start date.
        """
        self.task_3.planned_date_begin = False
        task3_date_deadline = self.task_3.date_deadline
        res = self.gantt_reschedule_maintain_buffer(self.task_1, self.task_1_date_gantt_reschedule_trigger())
        self.assertEqual(self.task_1.planned_date_begin, datetime(2021, 6, 24, 13))
        self.assertEqual(self.task_1.date_deadline, datetime(2021, 6, 24, 14))
        # Task 3 and its children 4, 5 and 6 remains unchanged
        self.assertFalse(self.task_3.planned_date_begin)
        self.assertEqual(self.task_3.date_deadline, task3_date_deadline)
        self.assert_task_not_replanned(self.task_4 | self.task_5 | self.task_6, self.project_pigs_intial_dates())
        self.assertEqual(res['message'], "Tasks rescheduled")

    def test_gantt_reschedule_backward_dependent_task_maintain_buffer_with_missing_date_deadline_on_task(self):
        """
            Tests backward rescheduling with maintain buffer when a depends on task (Task 4) has no date deadline.
            Task 6 -> task 5 should move to the left but Task 4 and its parent 3 and 1 remains unchanged due to
            Task 4 missing date deadline.
        """
        self.task_4.date_deadline = False
        task4_date_begin = self.task_4.planned_date_begin
        task_6_vals = {
            "planned_date_begin": '2021-08-03 08:00:00',
            "date_deadline": '2021-08-03 17:00:00'
        }
        res = self.gantt_reschedule_maintain_buffer(self.task_6, task_6_vals)
        self.assertEqual(self.task_6.planned_date_begin, datetime(2021, 8, 3, 8))
        self.assertEqual(self.task_6.date_deadline, datetime(2021, 8, 3, 17))
        self.assertEqual(self.task_5.planned_date_begin, datetime(2021, 6, 30, 8))
        self.assertEqual(self.task_5.date_deadline, datetime(2021, 8, 2, 17))
        # Task 4 and its parent 3 and 1 remains unchanged
        self.assertFalse(self.task_4.date_deadline)
        self.assertEqual(self.task_4.planned_date_begin, task4_date_begin)
        self.assert_task_not_replanned(self.task_3 | self.task_1, self.project_pigs_intial_dates())
        self.assertEqual(res['message'], "Tasks rescheduled")

    @users('admin')
    def test_gantt_reschedule_with_allocated_hours(self):
        """ This test purpose is to ensure that the task planned_date_fields (begin/end) are calculated accordingly to
            the allocated_hours if any. So if a dependent task has to be move forward up to before an unavailable period
            of time and that its allocated_hours is such that the date_deadline would fall into that unavailable
            period, then the date_deadline will be push forward after the unavailable period so that the
            allocated_hours constraint is met.

            task 3 is planned from 13H to 15H but with allocated hours = 8, when it will be moved, it will be planned
            in coherence with its allocated hours
        """
        self.task_3.allocated_hours = 8
        self.gantt_reschedule_consume_buffer(self.task_1, self.task_1_date_gantt_reschedule_trigger())
        failed_message = ("The auto shift date feature should take the allocated_hours into account and update the"
                         "date_deadline accordingly when moving a task forward.")
        self.assertEqual((self.task_3.planned_date_begin, self.task_3.date_deadline), (datetime(2021, 6, 24, 14, 0), datetime(2021, 6, 25, 14, 0)), failed_message + "8 hours between dates")

    @users('admin')
    def test_gantt_reschedule_without_allocated_hours(self):
        """ This test purpose is to ensure that the interval made by the task planned_date_fields (begin/end) is
            preserved when no allocated_hours is set.

            task 3 allocated hours = 0, task duration when moving it will be 2H as the difference between dates
        """
        self.task_3.write({
            'allocated_hours': 0,
        })
        self.gantt_reschedule_consume_buffer(self.task_1, self.task_1_date_gantt_reschedule_trigger())
        failed_message = ("The auto shift date feature should take the allocated_hours into account and update the"
                         "date_deadline accordingly when moving a task forward.")
        self.assertEqual((self.task_3.planned_date_begin, self.task_3.date_deadline), (datetime(2021, 6, 24, 14, 0), datetime(2021, 6, 24, 16, 0)), failed_message + "2 hours between dates")

    def test_gantt_reschedule_project_user(self):
        """ This test purpose is to ensure that the project user has the sufficient rights to trigger a gantt
            reschedule.
        """
        new_task_6_planned_date_begin = self.task_5_planned_date_begin + timedelta(hours=1)
        self.gantt_reschedule_consume_buffer(self.task_6, {
            'planned_date_begin': new_task_6_planned_date_begin.strftime('%Y-%m-%d %H:%M:%S'),
            'date_deadline': (new_task_6_planned_date_begin + (self.task_6_date_deadline - self.task_6_planned_date_begin)).strftime('%Y-%m-%d %H:%M:%S'),
        })
        failed_message = "The auto shift date feature should handle correctly dependencies cascades."
        self.assertEqual(self.task_5.date_deadline,
                         new_task_6_planned_date_begin, failed_message)
        self.assertEqual(self.task_5.planned_date_begin,
                         datetime(year=2021, month=6, day=29, hour=9), failed_message)
        self.assertEqual(self.task_4.date_deadline,
                         self.task_5.planned_date_begin, failed_message)
        self.assertEqual(self.task_4.planned_date_begin,
                         datetime(year=2021, month=6, day=28, hour=16), failed_message)

    @users('admin')
    def test_project2_reschedule_cascading_forward(self):
        """
            This test concerns project2 tasks, when task 0 is moved ahead of task 8.
            As tasks 1, 2, 3 are children of 0, they should be done after it,
            they should also be moved forward in one of this 2 valid orders
                1- ['0', '1', '2', '3']
                2- ['0', '1', '3', '2']
                but it will be usually the first option as task 3 is the first in the dependent_ids of task 1
            All the other tasks should not move.
        """
        self.project2_task_1.dependent_ids = self.project2_task_1.dependent_ids.sorted(key=lambda t: t.name, reverse=True)
        self.gantt_reschedule_consume_buffer(self.project2_task_0, {
            "planned_date_begin": "2024-03-18 08:00:00",
            "date_deadline": "2024-03-18 12:00:00",
        })

        self.assert_task_not_replanned(
            self.project2_task_4 | self.project2_task_5 | self.project2_task_6 | self.project2_task_7 | self.project2_task_8 | self.project2_task_9 |
            self.project2_task_10 | self.project2_task_11 | self.project2_task_12 | self.project2_task_13 | self.project2_task_14,
            self.initial_dates,
        )

        self.assert_new_dates(
            self.project2_task_0,
            datetime(year=2024, month=3, day=18, hour=8),
            datetime(year=2024, month=3, day=18, hour=12),
        )

        self.assert_new_dates(
            self.project2_task_1,
            datetime(year=2024, month=3, day=18, hour=13),
            datetime(year=2024, month=3, day=18, hour=17),
            "task 1 duration = 4 Hours. 4 hours will be planned on 18/03/2024 from 13H to 17H"
        )

        self.assert_new_dates(
            self.project2_task_2,
            datetime(year=2024, month=3, day=19, hour=8),
            datetime(year=2024, month=3, day=19, hour=10),
            "task 2 duration = 2 Hours. 2 hours will be planned on 19/03/2024 from 8H to 10H"
        )

        self.assert_new_dates(
            self.project2_task_3,
            datetime(year=2024, month=3, day=19, hour=10),
            datetime(year=2024, month=3, day=19, hour=16),
            "task 3 duration = 5 Hours. 5 hours will be planned on 19/03/2024 from 10H to 16H"
        )

    @users('admin')
    def test_project2_reschedule_cascading_backward(self):
        """
            This test concerns project2 tasks, when the left arrow is clicked. task 8 should be moved behind task 0
            As tasks 4, 6, 5, 7 are ancestors for 8 and should be done before it, they should be moved backward.
            A valid topo order can be:
                1- ['8', '7', '5', '6', '4']
                2- ['8', '7', '6', '4', '5']
                it will be usually 2 as task 5 is the first in the depend_on_ids of task 7.
            9 and 10 should not be impacted as they are not ancestors of 8.
            We shouldn't have conflicts with 11, 12, 13 and 14 that are already planned in the past
            All the other tasks should not move.
        """
        self.project2_task_7.depend_on_ids = self.project2_task_7.depend_on_ids.sorted(key=lambda t: t.name)
        self.gantt_reschedule_consume_buffer(self.project2_task_8, {
            "planned_date_begin": "2024-02-27 10:00:00",
            "date_deadline": "2024-02-29 17:00:00",
        })
        self.assert_task_not_replanned(
            self.project2_task_0 | self.project2_task_1 | self.project2_task_2 | self.project2_task_3 | self.project2_task_9 |
            self.project2_task_10 | self.project2_task_11 | self.project2_task_12 | self.project2_task_13 | self.project2_task_14,
            self.initial_dates,
        )

        self.assert_new_dates(
            self.project2_task_8,
            datetime(year=2024, month=2, day=27, hour=10),
            datetime(year=2024, month=2, day=29, hour=17),
        )
        self.assert_new_dates(
            self.project2_task_7,
            datetime(year=2024, month=2, day=26, hour=15),
            datetime(year=2024, month=2, day=27, hour=10),
            """
                task 7 duration = 4 Hours.
                2 hours available on 27/02/2024 from 8H to 10H.
                2 hours available on 26/02/2024 from 15H to 17H.
            """
        )

        self.assert_new_dates(
            self.project2_task_6,
            datetime(year=2024, month=2, day=21, hour=13),
            datetime(year=2024, month=2, day=23, hour=17),
            """
                task 6 duration = 20 Hours.
                no hours available in 26/02/2024 as task 7 was planned from 15H to 17H
                and task 14 planned from 8H to 15H
                16 hours will be planned on 22/02 and 23/02
                4 hours will be planned on 21/02 from 13H to 17H
            """
        )

        self.assert_new_dates(
            self.project2_task_4,
            datetime(year=2024, month=2, day=19, hour=13),
            datetime(year=2024, month=2, day=21, hour=12),
            """
                task 4 duration = 16 Hours
                4 Hours on 19/02
                8 hours on 20/02
                4 hours on 21/02 from 8H to 12H
            """
        )

        self.assert_new_dates(
            self.project2_task_5, datetime(year=2024, month=2, day=15, hour=13),
            datetime(year=2024, month=2, day=19, hour=12),
            """
                task 5 duration = 16 Hours.
                4 hours will be planned on 19/02
                8 hours will be planned on 16/02
                4 hours will be planned on 15 from 13H to 17H
            """
        )

    @users('admin')
    def test_project2_reschedule_cascading_backward_no_planning_in_the_past(self):
        """
        This test concerns project2 tasks, when the left arrow is clicked. task 8 should be moved behind task 0
        As tasks 4, 6, 5, 7 are ancestors for 8 and should be done before it, they should be moved backward.
        As we can't plan taks in the past and there are no available intervals to plan, so they should be
        planned starting from now and it will create conflicts

        fake now (01/04)                 07/04
                |                          |
                |                          |
                |                          |

                   [ 7 ]--->[8]----->[0]->[1]->[2]
                [ 6 ]
                [ 4 ]
                [ 5 ]
        """
        self.project2_task_0.planned_date_begin = datetime(year=2021, month=4, day=7, hour=8)
        res = self.gantt_reschedule_consume_buffer(self.project2_task_8, {
            "planned_date_begin": "2021-04-05 11:00:00",
            "date_deadline": "2021-04-06 17:00:00",
        })
        moved_tasks = self.project2_task_8 + self.project2_task_7 + self.project2_task_6 + self.project2_task_5 + self.project2_task_4
        self.assert_old_tasks_vals(res, 'info',
            'Some tasks were scheduled concurrently, resulting in a conflict due to the limited availability of the assignees. The planned dates for these tasks may not align with their allocated hours.',
            moved_tasks, self.initial_dates
        )

        self.assert_new_dates(
            self.project2_task_8,
            datetime(year=2021, month=4, day=5, hour=11),
            datetime(year=2021, month=4, day=6, hour=17),
        )

        self.assert_new_dates(
            self.project2_task_7,
            datetime(year=2021, month=4, day=2, hour=16),
            datetime(year=2021, month=4, day=5, hour=11),
            """
                task 7 duration = 4 Hours.
                5 hours to plan on 05/04 from 8H to 11H
                1 hour to plan on 02/04 from 16H to 17H
            """
        )

        self.assert_new_dates(
            self.project2_task_5,
            datetime(year=2021, month=4, day=1, hour=8),
            datetime(year=2021, month=4, day=2, hour=17),
            """
                task 5 duration = 16 Hours.
                No available slot to plan it, so it will be planned in conflict starting from the first available slot 01/04/2021
            """
        )

        self.assert_new_dates(
            self.project2_task_6,
            datetime(year=2021, month=4, day=1, hour=8),
            datetime(year=2021, month=4, day=5, hour=12),
            """
                task 6 duration = 20 Hours.
                No available slot to plan it, so it will be planned in conflict starting from the first available slot 01/04/2021
            """
        )

        self.assert_new_dates(
            self.project2_task_4,
            datetime(year=2021, month=4, day=1, hour=8),
            datetime(year=2021, month=4, day=2, hour=17),
            """
                task 4 duration = 16 Hours.
                No available slot to plan it, so it will be planned in conflict starting from the first available slot 01/04/2021
            """
        )

        moved_tasks.action_rollback_scheduling(res['old_vals_per_pill_id'])
        self.assert_task_not_replanned(moved_tasks, self.initial_dates)

    @users('admin')
    def test_compute_task_duration(self):
        """
            when task allocated_hours = 0, duration is computed as the intersection of work intervals and [planned_date_begin, date_deadline]
            example: task 6 is planned from datetime(2024, 3, 9, 8, 0) to datetime(2024, 3, 13, 12, 0)
            duration is 20:
            - 0 on 09/03 and 10/03 as it's weekend
            - 8 on 11/03
            - 8 on 12/03
            - 4 from 8H to 12H
        """
        durations = self.project2_task_6._get_tasks_durations(self.user_projectuser, 'planned_date_begin', 'date_deadline')
        self.assertEqual(durations[self.project2_task_6.id], 20 * 3600)

    @users('admin')
    def test_backward_cross_project(self):
        """
            When the move back/for{ward} concerns 2 tasks from 2 different projects, it's done
            exactly like the previous cases (tasks belonging to same project). There is nothing
            special for this case.

            Test dependencies Project     [5]---       ---->[6]---      -->[8]
                                               |       |         |      |
            project_pigs                       |    [4]-         --->[7]-
                                               |_________________|
        """
        self.project2_task_7.dependent_ids = self.project2_task_7.dependent_ids.sorted(key=lambda t: t.name)
        (self.project2_task_0 + self.project2_task_4 + self.project2_task_7).project_id = self.project_pigs.id
        self.gantt_reschedule_consume_buffer(self.project2_task_8, {
            "planned_date_begin": "2024-02-27 10:00:00",
            "date_deadline": "2024-02-29 17:00:00",
        })
        self.assert_task_not_replanned(
            self.project2_task_0 | self.project2_task_1 | self.project2_task_2 | self.project2_task_3 | self.project2_task_9 |
            self.project2_task_10 | self.project2_task_11 | self.project2_task_12 | self.project2_task_13 | self.project2_task_14,
            self.initial_dates,
        )

        self.assert_new_dates(
            self.project2_task_8,
            datetime(year=2024, month=2, day=27, hour=10),
            datetime(year=2024, month=2, day=29, hour=17),
            """
                task 8 duration = 13 Hours.
                Only 2 hours available on 29/02/2024 because task 12 and 13 are planned from 9H to 16H.
                Only 5 hours available on 28/02/2024 because task 11 is planned from 8H to 11H.
                The remaining 6 hours will be planned in 27/02/2024 from 10H
            """
        )
        self.assert_new_dates(
            self.project2_task_7,
            datetime(year=2024, month=2, day=26, hour=15),
            datetime(year=2024, month=2, day=27, hour=10),
            """
                task 8 duration = 4 Hours.
                2 hours available on 27/02/2024 from 8H to 10H.
                2 hours available on 26/02/2024 from 15H to 17H.
            """
        )

        self.assert_new_dates(
            self.project2_task_5,
            datetime(year=2024, month=2, day=15, hour=13),
            datetime(year=2024, month=2, day=19, hour=12),
            """
                task 5 duration = 16 Hours.
                day 17/02 and 18/02 are weekend
                4 hours planned on day 15/02
                8 hours planned on day 16/02
                4 hours planned on day 19/02
            """
        )

        self.assert_new_dates(
            self.project2_task_6,
            datetime(year=2024, month=2, day=21, hour=13),
            datetime(year=2024, month=2, day=23, hour=17),
            """
                task 6 duration = 20 Hours.
                4 Hours on 21/02, 16 Hours on 22/02 and 23/02
            """
        )

        self.assert_new_dates(
            self.project2_task_4,
            datetime(year=2024, month=2, day=19, hour=13),
            datetime(year=2024, month=2, day=21, hour=12),
            """
                task 4 duration = 16 Hours
                4 Hours on 19/02
                8 hours on 20/02
                4 hours on 21/02 from 8H to 12H
            """
        )

    def test_move_forward_with_multi_users(self):
        """
                        -------------------------------------------------
                        |                                               |
                        v                                               |
            Raouf 1    [0]->[ 1 ]------>[2]----------->[5]   |->[7]    [8]
                             |  |        ^      --------|----
                             |  |        |      |       |
            Raouf 2          |  -->[3]   |      |       ----->[9]----->[10]
                             |           |      |
                             |           |      |
            Raouf 3 and 2    ---------->[4]---->[6]

            When we move 0 in front of 8:
            - 3, 4 can be planned in // just after the end of 1
            - 2, 6 can be planned in // just after the end of 4
            - 5 planned after 2
            - 9, 10 should wait for 5 to be planned even if there are available slots before
            - 7 planned after 6
        """
        self.project2_task_8.write({
            'depend_on_ids': [Command.unlink(self.project2_task_7.id)],
        })
        (self.project2_task_4 + self.project2_task_6).write({
            'user_ids': [self.user2.id, self.user1.id],
        })

        (self.project2_task_9 + self.project2_task_10).write({
            'user_ids': [self.user1.id],
        })

        self.project2_task_2.write({
            'dependent_ids': [Command.link(self.project2_task_5.id)],
            'depend_on_ids': [Command.link(self.project2_task_4.id), Command.unlink(self.project2_task_7.id)],
        })

        self.project2_task_5.write({
            'dependent_ids': [Command.unlink(self.project2_task_7.id)]
        })

        self.project2_task_1.write({
            'dependent_ids': [Command.link(self.project2_task_4.id)]
        })

        res = self.gantt_reschedule_consume_buffer(self.project2_task_0, {
            "planned_date_begin": "2024-03-18 08:00:00",
            "date_deadline": "2024-03-18 12:00:00",
        })
        moved_tasks = self.project2.task_ids - self.project2_task_8 - self.project2_task_12 - self.project2_task_13 - self.project2_task_14 - self.project2_task_11
        self.assert_old_tasks_vals(res, 'success', 'Tasks rescheduled', moved_tasks, self.initial_dates)
        self.assert_new_dates(
            self.project2_task_0,
            datetime(year=2024, month=3, day=18, hour=8),
            datetime(year=2024, month=3, day=18, hour=12),
        )

        self.assert_new_dates(
            self.project2_task_1,
            datetime(year=2024, month=3, day=18, hour=13),
            datetime(year=2024, month=3, day=18, hour=17),
        )

        self.assert_new_dates(
            self.project2_task_3,
            datetime(year=2024, month=3, day=19, hour=8),
            datetime(year=2024, month=3, day=19, hour=14),
        )

        self.assert_new_dates(
            self.project2_task_4,
            datetime(year=2024, month=3, day=19, hour=8),
            datetime(year=2024, month=3, day=20, hour=17),
        )

        self.assert_new_dates(
            self.project2_task_2,
            datetime(year=2024, month=3, day=21, hour=8),
            datetime(year=2024, month=3, day=21, hour=10),
        )

        self.assert_new_dates(
            self.project2_task_6,
            datetime(year=2024, month=3, day=21, hour=8),
            datetime(year=2024, month=3, day=25, hour=12),
            "allocated_hours = 20"
        )

        self.assert_new_dates(
            self.project2_task_7,
            datetime(year=2024, month=3, day=25, hour=13),
            datetime(year=2024, month=3, day=25, hour=17),
        )

        self.assert_new_dates(
            self.project2_task_5,
            datetime(year=2024, month=3, day=21, hour=10),
            datetime(year=2024, month=3, day=25, hour=10),
        )

        self.assert_new_dates(
            self.project2_task_9,
            datetime(year=2024, month=3, day=25, hour=13),
            datetime(year=2024, month=3, day=25, hour=17),
            """
                task 9 should start after task 5 which is its blocking task and after task 6
                as user Raouf 2 was busy doing it.
            """
        )

        self.assert_new_dates(
            self.project2_task_10,
            datetime(year=2024, month=3, day=26, hour=8),
            datetime(year=2024, month=3, day=26, hour=12),
        )

        moved_tasks.action_rollback_scheduling(res['old_vals_per_pill_id'])
        self.assert_task_not_replanned(moved_tasks, self.initial_dates)

    def test_move_backward_with_multi_users(self):
        """
                         ----------------------------------------------------------------
                         |                                                              |
                         v                                                              |
            Armande     [13]    [0]->[ 1 ]------>[2]----------->[5]   |->[7]---------->[8]
                                      |  |        ^      --------|-----                 ^
                                      |  |        |      |       |                      |
            Raouf 2                   |  -->[3]   |      |       ----->[9]------------>[10]
                                      |           |      |
                                      |           |      |
            Raouf 3 & Raouf 2         ---------->[4]---->[6]

            When we move 8 before 13:
            - all the ancestors of 8 should move before 8 (0, 1, 4, 2, 6, 7, 5, 9, 10, 8)
        """
        self.project2_task_7.dependent_ids = self.project2_task_7.dependent_ids.sorted(key=lambda t: t.name)
        self.project2_task_8.write({
            'depend_on_ids': [Command.link(self.project2_task_10.id), Command.link(self.project2_task_7.id)],
            'dependent_ids': [Command.unlink(self.project2_task_0.id), Command.link(self.project2_task_13.id)],
        })

        (self.project2_task_4 + self.project2_task_6).write({
            'user_ids': [self.user2.id, self.user1.id],
        })

        (self.project2_task_9 + self.project2_task_10).write({
            'user_ids': [self.user1.id],
        })

        self.project2_task_2.write({
            'dependent_ids': [Command.link(self.project2_task_5.id)],
            'depend_on_ids': [Command.unlink(self.project2_task_7.id), Command.link(self.project2_task_4.id)],
        })

        self.project2_task_5.write({
            'dependent_ids': [Command.unlink(self.project2_task_7.id)]
        })

        self.project2_task_1.write({
            'dependent_ids': [Command.link(self.project2_task_4.id)]
        })

        res = self.gantt_reschedule_consume_buffer(self.project2_task_8, {
            "planned_date_begin": "2024-02-27 09:00:00",
            "date_deadline": "2024-02-29 09:00:00",
        })
        moved_tasks = self.project2.task_ids - self.project2_task_13 - self.project2_task_3 - self.project2_task_11 - self.project2_task_14 - self.project2_task_12
        self.assert_old_tasks_vals(res, 'success', 'Tasks rescheduled', moved_tasks, self.initial_dates)

        self.assert_new_dates(
            self.project2_task_0,
            datetime(year=2024, month=2, day=14, hour=9),
            datetime(year=2024, month=2, day=14, hour=14),
        )

        self.assert_new_dates(
            self.project2_task_1,
            datetime(year=2024, month=2, day=14, hour=14),
            datetime(year=2024, month=2, day=15, hour=9),
        )

        self.assert_new_dates(
            self.project2_task_4,
            datetime(year=2024, month=2, day=15, hour=9),
            datetime(year=2024, month=2, day=19, hour=9),
        )

        self.assert_new_dates(
            self.project2_task_2,
            datetime(year=2024, month=2, day=21, hour=15),
            datetime(year=2024, month=2, day=21, hour=17),
        )

        self.assert_new_dates(
            self.project2_task_6,
            datetime(year=2024, month=2, day=19, hour=9),
            datetime(year=2024, month=2, day=21, hour=14),
        )

        self.assert_new_dates(
            self.project2_task_7,
            datetime(year=2024, month=2, day=21, hour=14),
            datetime(year=2024, month=2, day=27, hour=9),
        )

        self.assert_new_dates(
            self.project2_task_5,
            datetime(year=2024, month=2, day=22, hour=8),
            datetime(year=2024, month=2, day=23, hour=17),
        )

        self.assert_new_dates(
            self.project2_task_9,
            datetime(year=2024, month=2, day=26, hour=9),
            datetime(year=2024, month=2, day=26, hour=14),
        )

        self.assert_new_dates(
            self.project2_task_10,
            datetime(year=2024, month=2, day=26, hour=14),
            datetime(year=2024, month=2, day=27, hour=9),
        )

        self.assert_new_dates(
            self.project2_task_8,
            datetime(year=2024, month=2, day=27, hour=9),
            datetime(year=2024, month=2, day=29, hour=9),
        )
        moved_tasks.action_rollback_scheduling(res['old_vals_per_pill_id'])
        self.assert_task_not_replanned(moved_tasks, self.initial_dates)

    def test_web_gantt_write(self):
        users = self.user_projectuser + self.user_projectmanager
        self.task_1.write({'user_ids': users.ids})
        self.task_2.write({'user_ids': self.user_projectuser.ids})
        tasks = self.task_1 + self.task_2
        tasks.web_gantt_write({'user_ids': self.user_projectmanager.ids})
        self.assertEqual(self.task_1.user_ids, users, "The assignees set on Task 1 should remain the same if the new assigne was in fact already in the assigness of the task.")
        self.assertEqual(self.task_2.user_ids, self.user_projectmanager, "The assignees set on Task 2 should be the new one and the user initially assinged should be unassigned.")

        tasks.web_gantt_write({'user_ids': False})
        self.assertFalse(tasks.user_ids, "No assignees should be set on the both tasks")

        tasks.web_gantt_write({'user_ids': self.user_portal.ids})
        self.assertEqual(self.task_1.user_ids, self.user_portal, "User portal should be assigned to Task 1.")
        self.assertEqual(self.task_2.user_ids, self.user_portal, "User portal should be assigned to Task 2.")

        tasks.web_gantt_write({'user_ids': users.ids})
        self.assertEqual(self.task_1.user_ids, users, "Project user and Prohect manager should be assigned to the task 1 and portal user should be assigned.")
        self.assertEqual(self.task_2.user_ids, users, "Project user and Prohect maanger should be assigned to the task 2 and portal user should be assigned.")

    def test_project_web_gantt_write(self):
        self.project_goats.write({
            'user_id': self.user_projectmanager.id,
        })
        self.project_pigs.write({
            'user_id': self.user_projectmanager.id,
            'date_start': '2021-09-27',
            'date': '2021-09-28'
        })
        self.project_goats.web_gantt_write({'user_id': False})
        self.assertEqual(
            self.project_goats.user_id,
            self.user_projectmanager,
            "Project without a schedule should retain its assignee when `user_id` is set to False"
        )

        self.project_pigs.web_gantt_write({'user_id': False})
        self.assertFalse(
            self.project_pigs.user_id,
            "Scheduled project should have its assignee removed when `user_id` is set to False."
        )
