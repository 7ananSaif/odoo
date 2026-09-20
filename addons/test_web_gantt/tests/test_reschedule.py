# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import Command
from odoo.tests import freeze_time
from .common import TestWebGantt


@freeze_time(datetime(2021, 1, 1))
class TestWebGanttReschedule(TestWebGantt):
    def test_reschedule_cascading_forward(self):
        """ This test purpose is to ensure that the forward rescheduling is properly working. """
        # 1- consume buffer
        res = self.gantt_reschedule_consume_buffer(self.pill_1, {
            self.date_start_field_name: "2021-06-01 00:00:00",
            self.date_stop_field_name: "2021-06-01 10:00:00",
        })
        moved_pills = self.pill_1 | self.pill_2 | self.pill_3 | self.pill_4
        self.assert_old_pills_vals(res, 'success', 'Tasks rescheduled', moved_pills, self.initial_dates)
        self.assertEqual(
            self.pill_1[self.date_stop_field_name], self.pill_2[self.date_start_field_name],
            'Pill 1 should move forward up to start of Pill 2.'
        )
        self.assertEqual(
            self.pill_2[self.date_stop_field_name], self.pill_3[self.date_start_field_name],
            'Pill 2 should move forward up to start of Pill 3.'
        )
        self.assertEqual(
            self.pill_3[self.date_stop_field_name], self.pill_4[self.date_start_field_name],
            'Pill 3 should move forward up to start of Pill 4.'
        )
        moved_pills.action_rollback_scheduling(res['old_vals_per_pill_id'])
        self.assert_not_replanned(moved_pills, self.initial_dates)

        # 2- maintain buffer
        res = self.gantt_reschedule_maintain_buffer(self.pill_1, {
            self.date_start_field_name: "2021-06-01 00:00:00",
            self.date_stop_field_name: "2021-06-01 10:00:00",
        })
        self.assert_old_pills_vals(res, 'success', 'Tasks rescheduled', moved_pills, self.initial_dates)
        self.assertEqual(
            self.pill_1[self.date_stop_field_name] + timedelta(seconds=self.buffer12), self.pill_2[self.date_start_field_name],
            'Pill 2 should start after buffer12 after the end of Pill 1.'
        )
        self.assertEqual(
            self.pill_2[self.date_stop_field_name] + timedelta(seconds=self.buffer23), self.pill_3[self.date_start_field_name],
            'Pill 3 should start after buffer12 after the end of Pill 2.'
        )
        self.assertEqual(
            self.pill_3[self.date_stop_field_name] + timedelta(seconds=self.buffer34), self.pill_4[self.date_start_field_name],
            'Pill 4 should start after buffer12 after the end of Pill 3.'
        )

    def test_reschedule_cascading_backward(self):
        """ This test purpose is to ensure that the backward rescheduling is properly working. """
        # 1- consume buffer
        res = self.gantt_reschedule_consume_buffer(self.pill_4, {
            self.date_start_field_name: "2021-03-01 00:00:00",
            self.date_stop_field_name: "2021-03-01 10:00:00",
        })
        moved_pills = self.pill_1 | self.pill_2 | self.pill_3 | self.pill_4
        self.assert_old_pills_vals(res, 'success', 'Tasks rescheduled', moved_pills, self.initial_dates)
        self.assertEqual(
            self.pill_1[self.date_stop_field_name], self.pill_2[self.date_start_field_name],
            'Pill 1 should move backward up to start of Pill 2.'
        )
        self.assertEqual(
            self.pill_2[self.date_stop_field_name], self.pill_3[self.date_start_field_name],
            'Pill 2 should move backward up to start of Pill 3.'
        )
        self.assertEqual(
            self.pill_3[self.date_stop_field_name], self.pill_4[self.date_start_field_name],
            'Pill 3 should move backward up to start of Pill 4.'
        )
        moved_pills.action_rollback_scheduling(res['old_vals_per_pill_id'])
        self.assert_not_replanned(moved_pills, self.initial_dates)

        # 2- maintain buffer
        res = self.gantt_reschedule_maintain_buffer(self.pill_4, {
            self.date_start_field_name: "2021-03-01 00:00:00",
            self.date_stop_field_name: "2021-03-01 10:00:00",
        })
        self.assert_old_pills_vals(res, 'success', 'Tasks rescheduled', moved_pills, self.initial_dates)
        self.assertEqual(
            self.pill_1[self.date_stop_field_name] + timedelta(seconds=self.buffer12), self.pill_2[self.date_start_field_name],
            'Pill 2 should start after buffer12 after the end of Pill 1.'
        )
        self.assertEqual(
            self.pill_2[self.date_stop_field_name] + timedelta(seconds=self.buffer23), self.pill_3[self.date_start_field_name],
            'Pill 3 should start after buffer12 after the end of Pill 2.'
        )
        self.assertEqual(
            self.pill_3[self.date_stop_field_name] + timedelta(seconds=self.buffer34), self.pill_4[self.date_start_field_name],
            'Pill 4 should start after buffer12 after the end of Pill 3.'
        )

    def test_not_in_past(self):
        """ This test purpose is to ensure that:
            * Records are not rescheduled in the past.
            * A notification is returned when trying to reschedule a record in the past.
        """
        res = self.gantt_reschedule_consume_buffer(self.pill_4, {
            self.date_start_field_name: "2021-01-01 00:00:00",
            self.date_stop_field_name: "2021-01-01 10:00:00",
        })
        self.assert_old_pills_vals(res, 'warning', 'Pill 3 cannot be scheduled in the past', self.env['test.web.gantt.pill'], self.initial_dates)

    def test_conflicting_cascade_forward(self):
        """
            ┌────────────────────────┐                                       ┌──────────────────────────────────┐
            │pill_2_slave_in_conflict|<---------- -------------------------->|  pill_2_slave_not_in_conflict    |
            └────────────────────────┘          | |                          └──────────────────────────────────┘
            ┌────────────────────────┐      ┌─────────┐     ┌─────────┐      ┌──────────────────────────────────┐
            │ Pill 1                 │ ---> │ Pill 2  │-->  │ Pill 3  │ -->  │ Pill 4                           │
            └────────────────────────┘      └─────────┘     └─────────┘      └──────────────────────────────────┘
            ┌────────────────────────┐                           | |         ┌──────────────────────────────────┐
            │pill_3_slave_in_conflict│<--------------------------- --------->│ pill_3_slave_not_in_conflict     │
            └────────────────────────┘                                       └──────────────────────────────────┘

            When moving forward without conflicts, we only move records in conflict.
            When advancing pill 3 without creating conflicts with pill_3_slave_not_in_conflict and pill 4, they both should not move.
            we only move pill_3_slave_in_conflict to fix the conflict
            ancestors should not be impacted
        """
        self.pill_2_slave_in_conflict = self.create_pill(
            'Pill in conflict with Pill 2', self.pill_1_start_date, self.pill_1_stop_date, [self.pill_2.id]
        )
        self.pill_2_slave_not_in_conflict = self.create_pill(
            'Pill not in conflict with Pill 2', self.pill_4_start_date, self.pill_4_stop_date, [self.pill_2.id]
        )
        self.pill_3_slave_in_conflict = self.create_pill(
            'Pill in conflict with Pill 3', self.pill_1_start_date, self.pill_1_stop_date, [self.pill_3.id]
        )
        self.pill_3_slave_not_in_conflict = self.create_pill(
            'Pill not in conflict with Pill 3', self.pill_4_start_date, self.pill_4_stop_date, [self.pill_3.id]
        )
        moved_pills = self.pill_3 | self.pill_3_slave_in_conflict
        initial_dates_deep_copy = dict(self.initial_dates)
        initial_dates_deep_copy[self.pill_3_slave_in_conflict.name] = (self.pill_3_slave_in_conflict.date_start, self.pill_3_slave_in_conflict.date_stop)

        res = self.gantt_reschedule_consume_buffer(self.pill_3, {
            self.date_start_field_name: "2021-03-04 00:00:00",
            self.date_stop_field_name: "2021-03-04 08:00:00",
        })

        self.assert_old_pills_vals(res, 'success', 'Tasks rescheduled', moved_pills, initial_dates_deep_copy)
        self.assertEqual(
            self.pill_3[self.date_stop_field_name],
            self.pill_4[self.date_start_field_name],
            'pill_3 should have been rescheduled to the start of pill_4'
        )
        self.assertEqual(
            self.pill_3_slave_in_conflict[self.date_start_field_name],
            self.pill_3[self.date_stop_field_name],
            'pill_3_slave_in_conflict should have been rescheduled once pill_3 had been rescheduled.'
        )
        self.assertEqual(
            self.pill_3_slave_not_in_conflict[self.date_start_field_name],
            self.pill_3[self.date_stop_field_name],
            'pill_3_slave_not_in_conflict should not be rescheduled once as it is not in conflict with pill_3.'
        )
        self.assertEqual(
            (self.pill_2[self.date_start_field_name], self.pill_2[self.date_stop_field_name]),
            (self.pill_2_start_date, self.pill_2_stop_date),
            'pill_2 should not be rescheduled.'
        )
        moved_pills.action_rollback_scheduling(res['old_vals_per_pill_id'])
        self.assert_not_replanned(moved_pills, initial_dates_deep_copy)

    def test_conflicting_cascade_backward(self):
        """
        ┌──────────────────────────────┐                                       ┌──────────────────────────────────┐
        |pill_2_master_not_in_conflict |----------- ---------------------------|  pill_2_master_in_conflict       |
        └──────────────────────────────┘          | |                          └──────────────────────────────────┘
                                                  v v
        ┌──────────────────────────────┐      ┌─────────┐     ┌─────────┐      ┌──────────────────────────────────┐
        │       Pill 1                 │ ---> │ Pill 2  │-->  │ Pill 3  │ -->  │ Pill 4                           │
        └──────────────────────────────┘      └─────────┘     └─────────┘      └──────────────────────────────────┘
                                                                   ^ ^
        ┌──────────────────────────────┐                           | |         ┌──────────────────────────────────┐
        | pill_3_master_not_in_conflict|---------------------------- ----------| pill_3_master_in_conflict        │
        └──────────────────────────────┘                                       └──────────────────────────────────┘

            When moving backward without conflicts, we only move records in conflict.
            When moving pill 2 to the end of pill 1 and pill_2_master_not_in_conflict without creating conflicts, they both should not move.
            we only move pill_2_master_in_conflict to fix the conflict
            children should not be impacted
        """
        self.pill_3_master_in_conflict = self.create_pill(
            'Pill in conflict with Pill 3', self.pill_4_start_date, self.pill_4_stop_date
        )
        self.pill_3_master_not_in_conflict = self.create_pill(
            'Pill not in conflict with Pill 3', self.pill_1_start_date, self.pill_1_stop_date
        )
        self.pill_3[self.dependency_field_name] = [
            Command.link(self.pill_3_master_in_conflict.id),
            Command.link(self.pill_3_master_not_in_conflict.id),
        ]
        self.pill_2_master_in_conflict = self.create_pill(
            'Pill in conflict with Pill 2', self.pill_4_start_date, self.pill_4_stop_date
        )
        self.pill_2_master_not_in_conflict = self.create_pill(
            'Pill not in conflict with Pill 2', self.pill_1_start_date, self.pill_1_stop_date
        )
        self.pill_2[self.dependency_field_name] = [
            Command.link(self.pill_2_master_in_conflict.id),
            Command.link(self.pill_2_master_not_in_conflict.id),
        ]
        moved_pills = self.pill_2 | self.pill_2_master_in_conflict
        initial_dates_deep_copy = dict(self.initial_dates)
        initial_dates_deep_copy[self.pill_2_master_in_conflict.name] = (self.pill_2_master_in_conflict.date_start, self.pill_2_master_in_conflict.date_stop)
        res = self.gantt_reschedule_consume_buffer(self.pill_2, {
            self.date_start_field_name: "2021-03-01 16:00:00",
            self.date_stop_field_name: "2021-03-02 00:00:00",
        })
        self.assert_old_pills_vals(res, 'success', 'Tasks rescheduled', moved_pills, initial_dates_deep_copy)
        self.assertEqual(self.pill_1[self.date_stop_field_name], self.pill_2[self.date_start_field_name])
        self.assertEqual(
            self.pill_2_master_in_conflict[self.date_stop_field_name],
            self.pill_2[self.date_start_field_name],
            'pill_2_master_in_conflict should have been rescheduled once pill_2 had been rescheduled.'
        )
        moved_pills.action_rollback_scheduling(res['old_vals_per_pill_id'])
        self.assert_not_replanned(moved_pills, initial_dates_deep_copy)

    def test_pills2_reschedule_cascading_forward(self):
        """
            This test concerns pills2, when pill 0 is move ahead of task 8.
            As pills 1, 2, 3 are children of 0, they should be done after it,
            they should also be moved forward
            All the other pills should not move.
        """
        self.gantt_reschedule_consume_buffer(self.pills2_0, {
            self.date_start_field_name: "2024-03-16 14:00:00",
            self.date_stop_field_name: "2024-03-16 18:00:00",
        })
        self.assert_not_replanned(
            self.pills2_4 | self.pills2_5 | self.pills2_6 | self.pills2_7 | self.pills2_8 | self.pills2_9 |
            self.pills2_10 | self.pills2_11 | self.pills2_12 | self.pills2_13 | self.pills2_14,
            self.initial_dates,
        )

        self.assertEqual(
            self.pills2_0[self.date_start_field_name],
            self.pills2_8[self.date_stop_field_name],
        )
        self.assertEqual(
            self.pills2_1[self.date_start_field_name],
            self.pills2_0[self.date_stop_field_name],
        )
        self.assertEqual(
            self.pills2_2[self.date_start_field_name],
            self.pills2_1[self.date_stop_field_name],
        )
        self.assertEqual(
            self.pills2_2[self.date_start_field_name],
            self.pills2_1[self.date_stop_field_name],
        )

    def test_pills2_reschedule_cascading_backward(self):
        """
            This test concerns pills2, when the left arrow is clicked. pill 8 should be moved behind pill 0
            As pills 4, 6, 5, 7 are ancestors for 8 and should be done before it, they should be moved backward.
            9 and 10 should not be impacted as they are not ancestors of 8.
            All the other pills should not move.
        """
        self.gantt_reschedule_consume_buffer(self.pills2_8, {
            self.date_start_field_name: "2024-03-01 02:00:00",
            self.date_stop_field_name: "2024-03-01 08:00:00",
        })
        self.assert_not_replanned(
            self.pills2_0 | self.pills2_1 | self.pills2_2 | self.pills2_3 | self.pills2_9 |
            self.pills2_10 | self.pills2_11 | self.pills2_12 | self.pills2_13 | self.pills2_14,
            self.initial_dates,
        )

        self.assertEqual(
            self.pills2_0[self.date_start_field_name],
            self.pills2_8[self.date_stop_field_name],
        )
        self.assertEqual(
            self.pills2_8[self.date_start_field_name],
            self.pills2_7[self.date_stop_field_name],
        )
        self.assertEqual(
            self.pills2_7[self.date_start_field_name],
            self.pills2_6[self.date_stop_field_name],
        )
        self.assertEqual(
            self.pills2_7[self.date_start_field_name],
            self.pills2_5[self.date_stop_field_name],
        )
        self.assertEqual(
            self.pills2_6[self.date_start_field_name],
            self.pills2_4[self.date_stop_field_name],
        )

    def test_dont_move_not_in_conflict(self):
        """
                                      ->[4]
                                      |
                                      ---------<-------
            [1]---------------------------->[2]->[3]--|

            When moving 3 before 4, 2 should also move to avoid creating conflicts, but 1
            should not be moved because with the new dates of 2 and 3, there is no
            conflict created.
        """
        self.pill_4.write({
            self.date_start_field_name: datetime(2021, 4, 27, 8, 0),
            self.date_stop_field_name: datetime(2021, 4, 27, 12, 0),
        })
        self.pill_2.write({
            self.date_start_field_name: datetime(2021, 4, 27, 13, 0),
            self.date_stop_field_name: datetime(2021, 4, 27, 17, 0),
        })
        self.pill_3.write({
            self.date_start_field_name: datetime(2021, 4, 28, 13, 0),
            self.date_stop_field_name: datetime(2021, 4, 28, 18, 0),
        })
        self.gantt_reschedule_consume_buffer(self.pill_3, {
            self.date_start_field_name: "2021-04-27 03:00:00",
            self.date_stop_field_name: "2021-04-27 08:00:00",
        })
        self.assertEqual(
            self.pill_3[self.date_stop_field_name],
            self.pill_4[self.date_start_field_name],
            '3 moved before 4',
        )
        self.assertEqual(
            self.pill_2[self.date_stop_field_name],
            self.pill_3[self.date_start_field_name],
            '2 moved before 3',
        )
        self.assert_not_replanned(self.pills2_1 | self.pills2_4, self.initial_dates)
