# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.addons.industry_fsm.tests.common import TestIndustryFsmCommon


@tagged('post_install', '-at_install')
class TestBaseDocumentLayout(TestIndustryFsmCommon):
    def test_get_render_information(self):
        DocumentLayout = self.env['base.document.layout'].with_context(active_model='project.task', active_id=self.task.id)
        document_layout = DocumentLayout.new()
        styles = document_layout._get_asset_style()
        # make sure no worksheet template is set to the task.
        self.task.worksheet_template_id = False
        render_information = document_layout._get_render_information(styles)
        self.assertEqual(render_information['doc'], self.task)
        self.assertNotIn(
            'worksheet_map',
            render_information,
            '`worksheet_map` key should not be in the dict returned since there is no worksheet created for the task.'
        )
        self.task.worksheet_template_id = self.env['worksheet.template'].create({
            'name': 'Test Default Worksheet',
            'res_model': 'project.task',
        })
        render_information = document_layout._get_render_information(styles)
        self.assertEqual(render_information['doc'], self.task)
        self.assertIn(
            'worksheet_map',
            render_information,
            '`worksheet_map` key should be in the dict returned by `_get_render_information` since there is a worksheet_template set on the task.'
        )
        self.assertEqual(
            render_information['worksheet_map'],
            {self.task.id: self.env[self.task.worksheet_template_id.model_id.model]},
            'The `worksheet_map` key should contain a dict with task_id as key and empty recordset of worksheet as value since there is no worksheet created for that task.'
        )
        worksheet_vals = {
            'x_name': 'This is a name',
            'x_comments': 'This is a comment',
            'x_project_task_id': self.task.id,
        }
        worksheet = self.env[self.task.worksheet_template_id.model_id.model].create(worksheet_vals)
        render_information = document_layout._get_render_information(styles)
        self.assertDictEqual(
            render_information['worksheet_map'],
            {self.task.id: worksheet},
            'worksheet_map key should contain a dict with task_id as key and the worksheet created for that task as value.'
        )
