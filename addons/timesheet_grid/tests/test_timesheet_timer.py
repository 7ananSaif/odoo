# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged

from odoo.addons.hr_timesheet.tests.test_timesheet import TestCommonTimesheet


@tagged('-at_install', 'post_install')
class TestTimesheetTimer(TestCommonTimesheet):
    def test_start_timer_in_timesheet(self):
        timesheet_without_task, timesheet = self.env['account.analytic.line'].with_user(self.user_employee).create([
            {'name': '/', 'project_id': self.project_customer.id, 'employee_id': self.empl_employee.id},
            {'name': '/', 'project_id': self.project_customer.id, 'task_id': self.task1.id, 'employee_id': self.empl_employee.id},
        ])
        timesheet_without_task.action_timer_start()
        timer = timesheet_without_task.user_timer_id
        self.assertTrue(timer, 'A timer should created for this timesheet.')
        self.assertEqual(timer.res_id, timesheet_without_task.id, 'The document linked to this timer should be the timesheet in which the user starts the timer.')
        self.assertEqual(timer.res_model, timesheet_without_task._name, 'The document model should be the one of the timesheet in which the timer is launched.')
        self.assertFalse(timer.parent_res_model, 'No Parent Document Model should be found since no task is linked to the timesheet in which the timer is launched.')
        self.assertFalse(timer.parent_res_id, 'No Parent Document should be found since no task is linked to the timesheet in which the timer is launched.')

        timesheet.action_timer_start()
        self.assertFalse(timesheet_without_task.user_timer_id, 'The previous timer should be stopped and removed since another timer will be created and launched.')
        timer = timesheet.user_timer_id
        self.assertTrue(timer, 'A timer should created for this timesheet.')
        self.assertEqual(timer.res_id, timesheet.id, 'The document linked to this timer should be the timesheet in which the user starts the timer.')
        self.assertEqual(timer.res_model, timesheet._name, 'The document model should be the one of the timesheet in which the timer is launched.')
        self.assertEqual(timer.parent_res_model, 'project.task', 'The parent document model should be the `project.task` model.')
        self.assertEqual(timer.parent_res_id, self.task1.id, 'The parent document should be the task linked to the timesheet in which the timer is launched.')

    def test_timer_in_task(self):
        """ Test the timer on a task """
        task = self.task1.with_user(self.user_employee)
        self.assertTrue(task.display_timesheet_timer, 'The timer should be available in that task.')
        task.action_timer_start()
        self.assertTrue(task.is_timer_running, 'The timer should be running and so the stop button appears on the task')
        action = task.action_timer_stop()
        self.assertEqual(action['res_model'], 'hr.timesheet.stop.timer.confirmation.wizard')
        wizard = self.env['hr.timesheet.stop.timer.confirmation.wizard'] \
            .with_context(action['context']) \
            .with_user(self.user_employee) \
            .new({})
        wizard.action_save_timesheet()
        self.assertFalse(task.timer_start, 'The stop button on the task is invisible')
        self.assertFalse(task.is_timer_running, 'The timer should be removed and so it is obviously no longer running.')

    def test_timer_sync_timesheet_to_task(self):
        """ Test sync between timesheet and task """
        timesheet = self.env['account.analytic.line'].with_user(self.user_employee).create({
            'name': "my timesheet 1",
            'project_id': self.project_customer.id,
            'task_id': self.task1.id,
            'date': fields.Date.today(),
            'unit_amount': 2.0,
            'employee_id': self.empl_employee.id,
        })

        # Start the timer on timesheet
        timesheet.action_timer_start()
        self.assertTrue(timesheet.is_timer_running, 'Timer should be started on timesheet')

        # Stop the timer from the task through the wizard
        task = self.task1.with_user(self.user_employee)
        self.assertTrue(task.user_timer_id, 'The timer in the task should be the one of the timesheet.')
        action = task.action_timer_stop()
        self.assertEqual(action['res_model'], 'hr.timesheet.stop.timer.confirmation.wizard')
        wizard = self.env['hr.timesheet.stop.timer.confirmation.wizard'] \
            .with_context(action['context']) \
            .with_user(self.user_employee) \
            .new({})
        wizard.action_save_timesheet()
        self.assertFalse(timesheet.is_timer_running, 'Timer should be stoped on Timesheet')

    def test_timer_sync_task_to_timesheet(self):
        """ Start the timer from the task and stop the timer from the timesheet """
        # start timer from the task
        task = self.task1.with_user(self.user_employee)
        with freeze_time(datetime.now() - relativedelta(minutes=1)):
            task.action_timer_start()
        self.assertTrue(bool(task.user_timer_id), 'A timer should be generated in the task.')
        timesheet = task.user_timer_id._get_related_document()
        self.assertIn(timesheet, task.timesheet_ids, 'A timesheet should be generated in the task in which the timer is started.')

        # stop timer from the timesheet
        timesheet.with_user(self.user_employee).action_timer_stop(True)
        self.assertFalse(task.user_timer_id, 'Timer should be stopped on ticket')
        self.assertGreater(timesheet.unit_amount, 0.0, 'unit_amount should be greated than his last value')

    def test_switch_timer_task(self):
        """
        Stop the running timer and log the timesheet entry on task when same user start the timer on another task
        """
        task1 = self.task1.copy()
        task2 = self.task1.copy()

        # Start the timer on task1
        with freeze_time(datetime.now() - relativedelta(minutes=1)):
            task1.with_user(self.user_employee).action_timer_start()

        # Start the timer on task2
        task2.with_user(self.user_employee).action_timer_start()
        self.assertFalse(task1.timer_start, 'Timer should be stoped on task1')
        self.assertEqual(len(task1.timesheet_ids), 1, 'Timesheet entry should be logged to the task1')
        self.assertEqual(len(task2.timesheet_ids), 1, 'Timesheet entry should be logged to the task2')

    def test_update_timesheet(self):
        """ Test if when the task is updated on the timesheet, the timer is also updated """
        timesheet = self.env['account.analytic.line'].with_user(self.user_employee).create({'name': '/', 'project_id': self.project_customer.id})
        timesheet.action_timer_start()
        timer = timesheet.user_timer_id
        self.assertTrue(bool(timer))
        self.assertFalse(timer.parent_res_model)
        self.assertFalse(timer.parent_res_id)

        timesheet.write({'task_id': self.task1.id})
        self.assertEqual(timer.parent_res_model, 'project.task')
        self.assertEqual(timer.parent_res_id, self.task1.id)

    def test_update_project_on_task_linked_to_timesheet_with_timer_running(self):
        """ Test if when the project is updated on the task linked to the timesheet with timer running, the timer is also updated """
        timesheet = self.env['account.analytic.line'] \
            .with_user(self.user_employee) \
            .create({
                'name': '/',
                'project_id': self.project_customer.id,
                'task_id': self.task1.id,
            })
        timesheet.action_timer_start()
        timer = timesheet.user_timer_id
        self.assertTrue(bool(timer))
        self.assertEqual(timer.res_id, timesheet.id)
        self.assertEqual(timer.res_model, timesheet._name)
        self.assertEqual(timer.parent_res_model, 'project.task')
        self.assertEqual(timer.parent_res_id, self.task1.id)

        timesheet_project, non_timesheetable_project = self.env['project.project'].create([
            {'name': 'Timesheet Project', 'allow_timesheets': True},
            {'name': 'Non Timesheet Project', 'allow_timesheets': False},
        ])
        self.task1.write({'project_id': timesheet_project.id})
        self.assertTrue(self.task1.with_user(self.user_employee).is_timer_running)
        self.assertEqual(timer.parent_res_model, 'project.task')
        self.assertEqual(timer.parent_res_id, self.task1.id)

        self.task1.write({'project_id': non_timesheetable_project.id})
        self.task1.invalidate_recordset()
        self.assertFalse(self.task1.with_user(self.user_employee).is_timer_running)
        self.assertFalse(timesheet.exists(), 'The timesheet should be removed since the timesheet has unit amount equals to 0.')

    def test_multi_company_start_timer(self):
        company = self.env['res.company'].create({'name': 'Company Test'})
        project = self.env['project.project'].create({
            'name': 'Test Project in Company Test',
            'allow_timesheets': True,
        })
        task = self.env['project.task'].create({
            'name': 'Test Task in Company Test',
            'project_id': project.id,
            'company_id': company.id,
        }).with_user(self.user_employee)
        self.assertFalse(self.task1.timesheet_ids)
        task1 = self.task1.with_user(self.user_employee)
        task1.action_timer_start()
        timer = task1.user_timer_id
        self.assertTrue(bool(timer))
        self.assertEqual(timer.parent_res_model, 'project.task')
        self.assertEqual(timer.parent_res_id, task1.id)
        timesheet_with_timer_running = self.env[timer.res_model].browse(timer.res_id)
        self.assertTrue(timesheet_with_timer_running, 'A timer should generate a timesheet')
        self.assertEqual(timesheet_with_timer_running.task_id, task1, 'The timesheet generated by the timer should be linked to the task1.')

        self.user_employee.company_ids += company
        self.env['hr.employee'].create({
            'name': 'Employee Test Company',
            'user_id': self.user_employee.id,
            'company_id': company.id,
        })
        task.with_company(company).action_timer_start()
        timer = task.user_timer_id
        self.assertTrue(bool(timer))
        self.assertEqual(timer.parent_res_model, 'project.task')
        self.assertEqual(timer.parent_res_id, task.id)
        self.assertFalse(task1.user_timer_id, 'The previous timer should be stopped since another timer is started.')
        self.assertTrue(timesheet_with_timer_running, 'A timesheet should still be there even if the timer is stopped.')
        self.assertFalse(timesheet_with_timer_running.with_user(self.user_employee).user_timer_id)
