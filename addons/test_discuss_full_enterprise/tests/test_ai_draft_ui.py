from odoo import Command
from odoo.tests import tagged, HttpCase
from unittest.mock import patch


@tagged('post_install', '-at_install')
class TestAIDraftUI(HttpCase):
    def _dummy_ai_submit_to_model(self, prompt, chat_history=None, extra_system_context=""):
        # ensure that record data is sent with the user message
        self.assertIn("The following JSON contains all of the record's details:", extra_system_context)
        return ["This is dummy ai response"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        project = cls.env['project.project'].create({
            'name': 'Test Project',
        })
        stage = cls.env['project.task.type'].create([{
            'name': 'Test Stage',
            'project_ids': project.ids,
        }])
        cls.env['project.task'].create({
            'name': 'Test task',
            'project_id': project.id,
            'stage_id': stage.id,
            'partner_id': cls.env['res.partner'].create({
                'name': 'Freddy',
                'email': 'freddy@example.com',
            }).id,
        })
        cls.env.ref('base.user_admin').write({
            'email': 'mitchell.admin@example.com'
        })
        cls.env['ai.composer'].create({
            'name': 'agent composer',
            'interface_key': 'chatter_ai_button',
            'focused_models': [cls.env['ir.model']._get_id('chatbot.script')],
            'available_prompts': [Command.create({
                'name': 'chatbot prompt button',
            })],
        })

    def test_ai_draft_chatter_button(self):
        with patch.object(self.env.registry['ai.agent'], '_generate_response', self._dummy_ai_submit_to_model):
            self.start_tour("/odoo", 'test_ai_draft_chatter_button', login='admin')

    def test_ai_draft_html_field(self):
        with patch.object(self.env.registry['ai.agent'], '_generate_response', self._dummy_ai_submit_to_model):
            self.start_tour("/odoo", 'test_ai_draft_html_field', login='admin')
