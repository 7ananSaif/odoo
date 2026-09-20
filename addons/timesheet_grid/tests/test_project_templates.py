from datetime import date, datetime

from odoo.tests import TransactionCase, freeze_time


@freeze_time("2025-07-17")  # Thursday
class TestProjectTemplates(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.irregular_calendar = cls.env["resource.calendar"].create({
            "name": "Irregular 3.5-day Week",
            "attendance_ids": [
                (0, 0, {"name": "Monday Morning", "dayofweek": "0", "hour_from": 9, "hour_to": 12}),
                (0, 0, {"name": "Monday Evening", "dayofweek": "0", "hour_from": 13, "hour_to": 17}),
                (0, 0, {"name": "Tuesday Morning", "dayofweek": "1", "hour_from": 9, "hour_to": 12}),
                (0, 0, {"name": "Thursday Morning", "dayofweek": "3", "hour_from": 9, "hour_to": 12}),
                (0, 0, {"name": "Thursday Evening", "dayofweek": "3", "hour_from": 13, "hour_to": 17}),
            ],
            "tz": "UTC",
        })
        cls.env.company.resource_calendar_id = cls.irregular_calendar.id

        cls.template_project = cls.env["project.project"].create({
            "name": "Template",
            "date_start": date(2025, 6, 2),  # Monday
            "date": date(2025, 6, 30),
            "is_template": True,
        })

    def test_create_project_from_template_with_company_calendar(self):
        self.env["project.task"].create({
            "name": "Task",
            "project_id": self.template_project.id,
            "planned_date_begin": datetime(2025, 6, 2, 9, 0),   # Tuesday
            "date_deadline": datetime(2025, 6, 5, 17, 0),       # Thursday
            "allocated_hours": 17,
        })

        # Will default to starting today (2025-07-17)
        new_project = self.template_project.action_create_from_template({
            "name": "New Project",
            "is_template": False,
        })
        copied_task = new_project.task_ids

        self.assertEqual(
            copied_task.planned_date_begin,
            datetime(2025, 7, 17, 9, 0),
            "Copied task should begin at the start of the day, on the first day of the created project.",
        )

        self.assertEqual(
            copied_task.date_deadline,
            datetime(2025, 7, 22, 12, 0),   # Tuesday
            "Copied task should end 17 working hours after its start.",
        )

    def test_planned_and_unplanned_tasks(self):
        self.env["project.task"].create([{
            "name": "A Planned Task",
            "project_id": self.template_project.id,
            "planned_date_begin": datetime(2025, 6, 4, 9, 0),   # Wednesday
            "date_deadline": datetime(2025, 6, 5, 17, 0),       # Thursday
            "allocated_hours": 17,
        }, {
            "name": "B Unplanned Task",
            "project_id": self.template_project.id,
        }])

        # Will default to starting today (2025-07-17)
        new_project = self.template_project.action_create_from_template({
            "name": "New Project",
            "is_template": False,
        })
        copied_planned, copied_unplanned = sorted(new_project.task_ids, key=lambda t: t.name)

        # Planned task expected start:
        # new project start + 2 days offset = Sat 2025-07-19 (non-working)
        # Shift to next working day Mon 2025-07-21 09:00
        expected_planned_start = datetime(2025, 7, 21, 9, 0)
        self.assertEqual(
            copied_planned.planned_date_begin,
            expected_planned_start,
            "Planned task should start offset by 2 days from project start, adjusted for calendar.",
        )
        self.assertEqual(
            copied_planned.allocated_hours,
            17,
            "Allocated hours for planned task should be preserved.",
        )
        self.assertFalse(
            copied_unplanned.planned_date_begin,
            "Unplanned tasks should remain unplanned.",
        )

    def test_create_from_future_template(self):
        self.template_project.write({
            "date_start": date(2025, 8, 4),  # Monday
            "date": date(2025, 8, 31),
        })
        self.env["project.task"].create({
            "name": "Future Task",
            "project_id": self.template_project.id,
            "planned_date_begin": datetime(2025, 8, 11, 9, 0),  # Monday, 7 days after start of project
            "date_deadline": datetime(2025, 8, 14, 17, 0),      # Thursday
            "allocated_hours": 17,
        })
        new_project = self.template_project.action_create_from_template({
            "name": "New From Future Template",
            "is_template": False,
        })
        copied_task = new_project.task_ids
        self.assertEqual(
            copied_task.planned_date_begin,
            datetime(2025, 7, 24, 9, 0),    # Thursday
            "Copied task should start 7 days from now.",
        )
        self.assertEqual(
            copied_task.date_deadline,
            datetime(2025, 7, 29, 12, 0),   # Tuesday
            "Copied task should end 17 working hours after its start.",
        )

    def test_unplanned_template_with_planned_tasks(self):
        """
        If the template has no dates, the planned tasks should get planned from the start date of the new project
        (by default, today)
        """
        self.template_project.write({
            "date_start": False,
            "date": False,
            'allow_task_dependencies': True,
        })

        task_1, task_2 = self.env["project.task"].create([{
            "name": "A Task",
            "project_id": self.template_project.id,
            "planned_date_begin": datetime(2025, 6, 2, 9, 0),   # Monday
            "date_deadline": datetime(2025, 6, 3, 10, 0),       # -> Tuesday 10 am = 8h
            "allocated_hours": 8,
        }, {
            "name": "B Task",
            "project_id": self.template_project.id,
            "planned_date_begin": datetime(2025, 6, 3, 10, 0),   # after Task A finishes
            "date_deadline": datetime(2025, 6, 5, 11, 0),        # -> Thursday 11 am = 4h
            "allocated_hours": 4,
        }])
        task_1.dependent_ids = task_2

        new_project = self.template_project.action_create_from_template({
            "name": "New Project",
            "is_template": False,
        })
        copied_task_1, copied_task_2 = sorted(new_project.task_ids, key=lambda t: t.name)

        self.assertEqual(
            copied_task_1.planned_date_begin,
            datetime(2025, 7, 17, 9, 0),    # Thursday
            "First copied task should start today at 09:00.",
        )
        self.assertEqual(
            copied_task_1.date_deadline,
            datetime(2025, 7, 21, 10, 0),   # Monday
            "First copied task should end after 8 working hours.",
        )

        # Task 2 should be planned right after task 1
        self.assertEqual(
            copied_task_2.planned_date_begin,
            datetime(2025, 7, 21, 10, 0),   # Monday
            "Second copied task should start when the first finishes.",
        )
        self.assertEqual(
            copied_task_2.date_deadline,
            datetime(2025, 7, 21, 15, 0),   # Monday
            "Second copied task should also last 4 working hours",
        )
        self.assertIn(
            copied_task_2, copied_task_1.dependent_ids,
            "Copied dependency between tasks should be preserved.",
        )

        new_project_2 = self.template_project.action_create_from_template({
            "name": "New Project",
            "is_template": False,
            "date_start": datetime(2025, 7, 22, 12, 0),
            "date": datetime(2025, 8, 22, 12, 0),
        })
        copied_task_3, copied_task_4 = sorted(new_project_2.task_ids, key=lambda t: t.name)

        self.assertEqual(
            copied_task_3.planned_date_begin,
            datetime(2025, 7, 22, 9, 0),    # Tuesday
            "First copied task should start at the project start date.",
        )
        self.assertEqual(
            copied_task_3.date_deadline,
            datetime(2025, 7, 24, 15, 0),   # Thursday
            "First copied task should end after 8 working hours.",
        )

        self.assertEqual(
            copied_task_4.planned_date_begin,
            datetime(2025, 7, 24, 15, 0),   # Thursday
            "Second copied task should start when the first finishes.",
        )
        self.assertEqual(
            copied_task_4.date_deadline,
            datetime(2025, 7, 28, 11, 0),   # Monday
            "Second copied task should also last 4 working hours.",
        )
