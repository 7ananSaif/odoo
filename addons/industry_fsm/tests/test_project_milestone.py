# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo.tests import Form, tagged

from odoo.addons.project.tests.test_project_base import TestProjectCommon


@tagged('-at_install', 'post_install')
class TestProjectMilestone(TestProjectCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_pigs.write({'is_fsm': True})

    def test_milestones_settings_change(self):
        self.env.user.group_ids |= self.env.ref('project.group_project_milestone')
        Project = self.env['project.project'].with_context({'mail_create_nolog': True})
        fsm_project = Project.with_context(default_is_fsm=True).create({
            'name': 'Test allow_milestones on New FSM Project',
        })
        self.assertFalse(fsm_project.allow_milestones, 'The "Milestones" feature should not be enabled by default on New FSM project even if the feature is globally enabled')

        with self.debug_mode():
            with Form(Project) as project_form:
                project_form.name = 'My Mouses Project'
                self.assertFalse(project_form.allow_milestones, 'New projects allow_milestones should be False by default.')
                project_form.is_fsm = True
                self.assertFalse(project_form.allow_milestones, 'When the project becomes a FSM one the `allow_milestones` should be equal to False by default.')
