from datetime import timedelta

from .common import TestWebGantt


class TestActionUndo(TestWebGantt):

    def test_undo_pill_rescheduling(self):
        initial_schedule = {
            'date_start': self.pill_1_start_date,
            'date_stop': self.pill_1_stop_date,
        }
        # Reschedule the pill
        self.pill_1.date_start = self.pill_1_start_date + timedelta(days=3)
        self.pill_1.date_stop = self.pill_1_stop_date + timedelta(days=3)
        # Undo the rescheduling
        self.pill_1.gantt_undo_drag_drop('reschedule', initial_schedule)
        self.assertEqual(
            self.pill_1.date_start,
            self.pill_1_start_date,
            'Pill start date should be reset to its initial value',
        )
        self.assertEqual(
            self.pill_1.date_stop,
            self.pill_1_stop_date,
            'Pill stop date should be reset to its initial value',
        )

    def test_undo_pill_copy(self):
        # Copy the pill
        pill_copy = self.pill_1.copy()
        # Undo the copy
        pill_copy.gantt_undo_drag_drop('copy')
        self.assertFalse(pill_copy.exists(), 'Pill copy should be deleted')
