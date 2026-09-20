# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo.tests import Form, tagged

from odoo.addons.project.tests.test_project_base import TestProjectCommon


@tagged('-at_install', 'post_install')
class TestBasicFeaturesSettings(TestProjectCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.project_pigs.write({
            'is_fsm': True,
        })

    def test_basic_features(self):
        for group_flag, project_flag in (
            ('project.group_project_task_dependencies', 'allow_task_dependencies'),
            ('project.group_project_milestone', 'allow_milestones'),
            ('project.group_project_recurring_tasks', 'allow_recurring_tasks'),
        ):
            self._test_basic_feature(group_flag, project_flag)

    def _test_basic_feature(self, group_flag, project_flag):
        self.env.user.group_ids |= self.env.ref(group_flag)

        self.assertFalse(self.project_pigs[project_flag], f"FSM Projects should not follow {group_flag} changes")

        with self.debug_mode():
            with Form(self.env['project.project']) as project_form:
                project_form.name = 'My Ducks Project'
                project_form.is_fsm = True
                self.assertFalse(project_form[project_flag], f"The {project_flag} feature should be disabled by default on new FSM projects")

        self.project_pigs.write({project_flag: True})
        self.assertTrue(self.project_pigs[project_flag], f"The {project_flag} feature should be enabled on the project")
