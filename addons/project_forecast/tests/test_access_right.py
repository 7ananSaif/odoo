# Part of Odoo. See LICENSE file for full copyright and licensing details

from .common import TestCommonForecast
from odoo import Command
from odoo.tests import new_test_user


class TestForecastAccessRights(TestCommonForecast):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.setUpEmployees()
        cls.setUpProjects()

        cls.user_projectuser = new_test_user(cls.env, login='project_user', groups='project.group_project_user')
        cls.user_projectmanager = new_test_user(cls.env, login='project_manager', groups='project.group_project_manager')

        cls.private_project_1, cls.private_project_2 = cls.env['project.project'].create([
            {
                'name': 'Private project 1',
                'privacy_visibility': 'followers',
                'message_partner_ids': [Command.set([cls.user_projectuser.partner_id.id])],
            }, {
                'name': 'Private project 2',
                'privacy_visibility': 'followers',
                'message_partner_ids': [Command.set([cls.user_projectmanager.partner_id.id])],
            },
        ])

        # Create planning slot templates related to these private projects
        cls.PlanningSlotTemplates = cls.env['planning.slot.template']
        cls.slot_templates = cls.PlanningSlotTemplates.create([
            {'name': 'Template 1', 'project_id': cls.private_project_1.id, 'start_time': 11, 'end_time': 16},
            {'name': 'Template 2', 'project_id': cls.private_project_2.id, 'start_time': 11, 'end_time': 16},
            {'name': 'Template 3', 'start_time': 11, 'end_time': 16},
        ])

    def test_project_manager_access_slot_template(self):
        """Test that a project manager can access all planning slot templates."""
        slot_templates_count = self.PlanningSlotTemplates.with_user(self.user_projectmanager).search_count([('id', 'in', self.slot_templates.ids)])
        self.assertEqual(slot_templates_count, 3, "Project manager should have access to all planning slots template.")

    def test_project_user_access_slot_template(self):
        """Test that a project user can access only specific planning slot templates."""
        slot_templates = self.PlanningSlotTemplates.with_user(self.user_projectuser).search([('id', 'in', self.slot_templates.ids)])
        self.assertEqual(len(slot_templates), 2, "Project users should have access to specific project and non-project templates.")
        self.assertTrue(
            self.slot_templates[1] not in slot_templates,
            "The slot template linked to the second private project should not be accessible to the project user if he does not have access to the project linked."
        )
