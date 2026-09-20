# Part of Odoo. See LICENSE file for full copyright and licensing details
from datetime import date, datetime

from odoo.addons.project_forecast.tests.common import TestCommonForecast

from odoo.tests import freeze_time


class TestPlanningTimesheet(TestCommonForecast):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.setUpEmployees()
        cls.setUpProjects()

    def test_gantt_progress_bar_group_by_project(self):
        """
        This test ensures that the _gantt_progress_bar_project_id return values is correct.
        - Every project_id present in the res_ids should be present in the dict.
        - The 'value' should be 0 if the project contains no planning slot available in the date range given, else it should be equal to the total of every available slot for the given date range.
        - The 'max value' should be equal to the 'allocated_hours' field for each project.
        """
        projects = project_without_slot, project_slot_not_in_date_range, project_slot_in_date_range = self.env['project.project'].with_context(tracking_disable=True).create([{
            'name': 'Project no slot',
            'allocated_hours': 40,
        }, {
            'name': 'Project slot not in date range',
            'allocated_hours': 50,
        }, {
            'name': 'Project slot in date range',
            'allocated_hours': 60,
        }])
        start_date = datetime(2021, 10, 22, 8, 0, 0)
        end_date = datetime(2021, 10, 29, 8, 0, 0)
        planning_vals = {
            'resource_id': self.resource_joseph.id,
            'state': 'published',
            'allow_timesheets': True,
        }
        self.env["planning.slot"].create([{
            **planning_vals,
            'project_id': project_slot_in_date_range.id,
            'start_datetime': datetime(2021, 10, 25, 8, 0, 0),
            'end_datetime': datetime(2021, 10, 26, 12, 0, 0),
        }, {
            **planning_vals,
            'project_id': project_slot_in_date_range.id,
            'start_datetime': datetime(2021, 10, 26, 13, 0, 0),
            'end_datetime': datetime(2021, 10, 26, 17, 0, 0),
        }, {
            **planning_vals,
            'project_id': project_slot_not_in_date_range.id,
            'start_datetime': datetime(2021, 10, 20, 8, 0, 0),
            'end_datetime': datetime(2021, 10, 21, 12, 0, 0),
        }])
        res_ids = projects.ids
        expected_values = {
            project_without_slot.id: {'value': 0.0, 'max_value': 40.0},
            project_slot_not_in_date_range.id: {'value': 0.0, 'max_value': 50.0},
            project_slot_in_date_range.id: {'value': 16.0, 'max_value': 60.0}, # 12 hours in the 1st slot + 4 hours in the 2nd slot
        }
        values = self.env["planning.slot"]._gantt_progress_bar_project_id(res_ids, start_date, end_date)
        self.assertDictEqual(values, expected_values)

    @freeze_time('2019-06-06 01:00:00')
    def test_timesheets_forecast_analysis_with_weekend_included(self):
        self.project_opera.write({'allow_timesheets': True})
        self.env['planning.slot'].create({
            'project_id': self.project_opera.id,
            'employee_id': self.employee_bert.id,
            'resource_id': self.resource_bert.id,
            'allocated_hours': 40,
            'start_datetime': datetime(2019, 6, 6, 8, 0, 0),
            # 6/8/2019 and 6/9/2019 are weekend days
            'end_datetime': datetime(2019, 6, 12, 17, 0, 0),
            'allocated_percentage': 100,
            'state': 'draft',
        })
        self.env['planning.slot'].flush_model()
        result = self.env['project.timesheet.forecast.report.analysis'].formatted_read_group(
            domain=[["project_id", "=", self.project_opera.id]],
            groupby=["entry_date:month"],
            aggregates=["planned_hours:sum"],
        )
        self.assertEqual((result[0]['planned_hours:sum']), 40)

    def test_compute_slot_effective_hours(self):
        slot = self.env["planning.slot"].create({
            'resource_id': self.employee_bert.resource_id.id,
            'project_id': self.project_opera.id,
            'start_datetime': datetime(2024, 1, 1, 8, 0, 0),
            'end_datetime': datetime(2024, 1, 31, 17, 0, 0),
        })
        self.assertEqual(slot.effective_hours, 0)
        self.env['account.analytic.line'].create({
            'name': 'Test Timesheet',
            'unit_amount': 2,
            'project_id': self.project_opera.id,
            'task_id': self.task_opera_place_new_chairs.id,
            'employee_id': self.employee_bert.id,
            'date': date(2024, 1, 15),
        })
        self.assertEqual(slot.effective_hours, 2)

    def test_planning_analysis_report_fields(self):
        ''' This test ensure that the fields of the planning analysis report are correctly computed'''
        slot = self.env["planning.slot"].create({
            'resource_id': self.employee_bert.resource_id.id,
            'project_id': self.project_opera.id,
            'start_datetime': datetime(2025, 1, 22, 0, 0, 0),
            'end_datetime': datetime(2025, 1, 23, 0, 0, 0),
            'state': 'published',
            'allow_timesheets': True,
        })
        self.env['account.analytic.line'].create({
            'name': 'Test Timesheet',
            'unit_amount': 2,
            'project_id': self.project_opera.id,
            'task_id': self.task_opera_place_new_chairs.id,
            'employee_id': self.employee_bert.id,
            'date': date(2025, 1, 22),
        })
        slot.invalidate_recordset()

        effective_hours, remaining_hours, percentage_hours = self.env['planning.analysis.report']._read_group(
            [('slot_id', '=', slot.id)],
            aggregates=['effective_hours:sum', 'remaining_hours:sum', 'percentage_hours:avg'],
        )[0]

        self.assertEqual(effective_hours, 2.0, "Effective hours should match the timesheet entry")
        self.assertEqual(remaining_hours, 6.0, "Remaining hours should be Allocated Hours - Effective hours")
        self.assertEqual(percentage_hours, 25.0, "Percentage hours should be calculated properly")
