# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from datetime import datetime

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged, users

from .common import TestIndustryFsmCommon

@tagged('post_install', '-at_install')
class TestFsmFlow(TestIndustryFsmCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['project.project'].create({
            'name': 'project 2',
            'privacy_visibility': 'followers',
        })

    def test_stop_timers_on_mark_as_done(self):
        self.assertEqual(len(self.task.sudo().timesheet_ids), 0, 'There is no timesheet associated to the task')
        timesheet = self.env['account.analytic.line'].with_user(self.marcel_user).create({'name': '', 'project_id': self.fsm_project.id})
        timesheet.action_add_time_to_timer(3)
        timesheet.action_change_project_task(self.fsm_project.id, self.task.id)
        self.assertTrue(timesheet.user_timer_id, 'A timer is linked to the timesheet')
        self.assertTrue(timesheet.user_timer_id.is_timer_running, 'The timer linked to the timesheet is running')
        task_with_henri_user = self.task.with_user(self.henri_user)
        task_with_henri_user.action_timer_start()
        self.assertTrue(task_with_henri_user.user_timer_id, 'A timer is linked to the task')
        self.assertTrue(task_with_henri_user.user_timer_id.is_timer_running, 'The timer linked to the task is running')
        task_with_george_user = self.task.with_user(self.george_user)
        result = task_with_george_user.action_fsm_validate()
        self.assertEqual(result['type'], 'ir.actions.act_window', 'As there are still timers to stop, an action is returned')
        Timer = self.env['timer.timer']
        tasks_running_timer_ids = Timer.search([('parent_res_model', '=', 'project.task'), ('parent_res_id', '=', self.task.id)])
        timesheets_running_timer_ids = Timer.search([('res_model', '=', 'account.analytic.line'), ('res_id', '=', timesheet.id)])
        self.assertEqual(len(timesheets_running_timer_ids), 1, 'There is still a timer linked to the timesheet')
        self.task.invalidate_model(['timesheet_ids'])
        self.assertEqual(len(tasks_running_timer_ids), 2, 'The both timers (one from marcel and the other from henri) should be linked to the task.')
        wizard = self.env['project.task.stop.timers.wizard'].create({'line_ids': [Command.create({'task_id': self.task.id})]})
        wizard.action_confirm()
        tasks_running_timer_ids = Timer.search([('res_model', '=', 'project.task'), ('res_id', '=', self.task.id)])
        timesheets_running_timer_ids = Timer.search([('res_model', '=', 'account.analytic.line'), ('res_id', '=', timesheet.id)])
        self.assertFalse(timesheets_running_timer_ids, 'There is no more timer linked to the timesheet')
        self.task.invalidate_model(['timesheet_ids'])
        self.assertFalse(tasks_running_timer_ids, 'There is no more timer linked to the task')
        self.assertEqual(len(self.task.sudo().timesheet_ids), 2, 'There are two timesheets')

    def test_mark_task_done_state_change(self):
        self.task.write({
            'state': '01_in_progress',
        })
        self.task.action_fsm_validate()
        self.assertEqual(self.task.state, '1_done', 'task state should change to done')

        second_task = self.env['project.task'].create({
            'name': 'Fsm task 2',
            'project_id': self.fsm_project.id,
            'partner_id': self.partner.id,
            'state': '02_changes_requested',
        })

        second_task.action_fsm_validate()
        self.assertEqual(second_task.state, '1_done', 'second task state should change to done')

    @users('Project user', 'Project admin', 'Base user')
    def test_base_user_no_create_stop_timers_wizard(self):
        with self.assertRaises(AccessError):
            self.env['project.task.stop.timers.wizard'].with_user(self.env.user).create({'line_ids': [Command.create({'task_id': self.task.id})]})

    @users('Fsm user')
    def test_fsm_user_can_create_stop_timers_wizard(self):
        self.env['project.task.stop.timers.wizard'].with_user(self.env.user).create({'line_ids': [Command.create({'task_id': self.task.id})]})

    def test_default_user_not_assigned_to_task(self):
        # Create a task without specifying the assignee.
        task = self.env['project.task'].with_context(fsm_mode=True).create({'name': 'New Task'})
        # Ensure that the default user is not set as the assignee.
        self.assertNotEqual(task.user_ids, self.env.user, "Default user should not be set as the assignee of the task.")

    def test_navigation_link(self):
        partner = self.env['res.partner'].create({
            'name': 'A Test Partner',
            'street': 'Chaussée de Namur 40',
            'zip': '1367',
            'city': 'Ramillies',
        })
        self.assertEqual(
            partner.action_partner_navigate()['url'],
            "https://www.google.com/maps/dir/?api=1&destination=Chauss%C3%A9e+de+Namur+40%2C+1367+Ramillies",
        )

    def test_fsm_project_default_task_types(self):
        self.assertTrue(self.fsm_project.type_ids, "FSM project should have default FSM task types assigned.")
        # Create a new FSM project
        new_fsm_project = self.env['project.project'].create({
            'name': 'New FSM Project',
            'is_fsm': True,
            'company_id': self.env.company.id
        })
        self.assertEqual(new_fsm_project.type_ids, self.fsm_project.type_ids, "New FSM project should inherit tasks stages from the existing FSM project.")

    def test_new_fsm_stage_linked_with_existing_project(self):
        """Check whether the new FSM stage is linked to the existing project or not."""
        Project = self.env['project.project']
        fsm_stage = self.env['project.task.type'].search([('project_ids.is_fsm', '=', True)])
        # To create a new stage; otherwise, the old FSM stage is linked.
        fsm_stage.action_archive()
        fsm_project_no_stages = Project.create({
            'name': 'New FSM Project',
            'is_fsm': True,
            'company_id': self.env.company.id,
            'type_ids': False,
        })
        fsm_project_with_stages = Project.with_context(fsm_mode=True).create({
            'name': 'New FSM Project',
            'is_fsm': True,
            'company_id': self.env.company.id,
        })
        self.assertFalse(
            fsm_project_no_stages.type_ids,
            "FSM Project without stages should not have any task stages."
        )
        self.assertTrue(
            fsm_project_with_stages.type_ids,
            "FSM Project with stages should have default task stages."
        )
        fsm_stage.action_unarchive()

    def test_plan_task_in_calendar(self):
        self.task.user_ids = self.george_user
        self.george_user.employee_id.resource_id.tz = 'UTC'
        self.task.with_context(task_calendar_plan_full_day=True).plan_task_in_calendar({
            'planned_date_begin': '2023-02-01 07:00:00',
            'date_deadline': '2023-02-01 19:00:00',
        })
        self.assertEqual(self.task.planned_date_begin, datetime(2023, 2, 1, 8, 0, 0))
        self.assertEqual(self.task.date_deadline, datetime(2023, 2, 1, 17, 0, 0))
        self.assertEqual(self.task.allocated_hours, 8)

    def test_start_timer_on_private_project(self):
        task = self.env['project.task'].create({
            'name': 'Task A',
            'project_id': self.project.id,
            'user_ids': self.project_user.ids,
        })
        self.employee_user.user_id = self.project_user
        self.project_user.group_ids += self.env.ref("hr_timesheet.group_hr_timesheet_user")
        task_with_employee_user = task.with_user(self.project_user)
        with self.assertRaises(AccessError):
            self.project.with_user(self.project_user).read(['name'])
        task_with_employee_user.action_timer_start()
        self.assertTrue(task_with_employee_user.user_timer_id)
        result = task_with_employee_user.action_timer_stop()
        wizard = self.env[result['res_model']] \
                     .with_context(result['context']) \
                     .with_user(self.project_user) \
                     .new()
        self.env['project.project'].invalidate_model()
        wizard.action_save_timesheet()
        self.assertEqual(wizard.timesheet_id.task_id, task)
        self.assertEqual(wizard.timesheet_id.project_id, self.project)

    def test_project_template_user_access(self):
        """
        test that checks that even if a user doesn't have enough rights to create a project from a template,
        the view will still open
        """
        project_template = self.env['project.project'].create({
            'name': 'Field Service',
            'is_fsm': True,
            'allow_timesheets': True,
            'company_id': self.env.company.id,
            'is_template': True,
            'date_start': '2023-02-01 07:00:00',
            'date': '2023-02-02 07:00:00',
            'user_id': self.george_user.id,
        })
        self.env['project.task'].create({
            'name': 'Task template',
            'project_id': project_template.id,
            'partner_id': self.partner.id,
            'user_ids': [Command.set([self.george_user.id])],
            'planned_date_begin': '2023-02-01 07:00:00',
            'date_deadline': '2023-05-01 19:00:00',
        })

        wizard = self.env['project.template.create.wizard'].create({
            'template_id': project_template.id,
            'name': 'New Project from Template',
            'date_start': '2023-02-01 07:00:00',
            'date': '2023-02-02 07:00:00',
        })
        self.fsm_user.group_ids |= self.env.ref('project.group_project_manager')
        env = self.env(user=self.fsm_user.id)
        new_project_view = wizard.with_env(env).create_project_from_template()
        self.assertEqual(new_project_view.get('type'), 'ir.actions.act_window')
