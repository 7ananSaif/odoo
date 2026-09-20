# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestIndustryFsmCommon


@tagged('post_install', '-at_install')
class TestBaseDocumentLayout(TestIndustryFsmCommon):
    def test_get_preview_template(self):
        DocumentLayout = self.env['base.document.layout']
        self.assertEqual(
            DocumentLayout._get_preview_template(),
            "web.report_invoice_wizard_preview",
            "The template should be the default one since there is no active_model and active_id inside the context."
        )
        self.assertEqual(
            DocumentLayout.with_context(active_model='foo.bar', active_id=self.task.id)._get_preview_template(),
            "web.report_invoice_wizard_preview",
            "The template should be the default one since the active_model is not `project.task` model name."
        )
        self.assertEqual(
            DocumentLayout.with_context(active_model='project.task')._get_preview_template(),
            "web.report_invoice_wizard_preview",
            "The template should be the default one since the active_id is not defined in the context."
        )

        # Add context to be able to check the override
        DocumentLayout = DocumentLayout.with_context(active_model='project.task', active_id=self.task.id)
        self.assertEqual(
            DocumentLayout._get_preview_template(),
            "industry_fsm.worksheet_custom_preview",
            "The template should be the industry_fsm one since the active_model is `project.task` and active_id is defined."
        )

    def test_get_render_information(self):
        DocumentLayout = self.env['base.document.layout'].with_context(active_model='project.task', active_id=self.task.id)
        document_layout = DocumentLayout.new()
        styles = document_layout._get_asset_style()
        render_information = document_layout._get_render_information(styles)
        self.assertEqual(render_information['doc'], self.task)
