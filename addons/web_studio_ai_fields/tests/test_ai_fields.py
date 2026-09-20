# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.web_studio.tests.test_view_editor import TestStudioController


class TestStudioAiFields(TestStudioController):
    def test_edit_ai_field(self):
        model = self.env['ir.model'].search([('model', '=', 'res.partner')])
        field = self.env['ir.model.fields'].with_context(studio=True).create({
            'ttype': 'char',
            'model_id': model.id,
            'name': 'x_test_ai_field',
        })
        self.assertFalse(field.ai)
        self.assertFalse(field.system_prompt)

        self.studio_controller.edit_field(model.model, field.name, {'ai': True})
        self.assertTrue(field.ai)
        self.assertFalse(field.system_prompt)

        self.studio_controller.edit_field(model.model, field.name, {'system_prompt': "<p>Hello</p>"})
        self.assertTrue(field.ai)
        self.assertEqual(field.system_prompt, "<p>Hello</p>")

        self.studio_controller.edit_field(model.model, field.name, {'ai': False})
        self.assertFalse(field.ai)
        self.assertFalse(field.system_prompt)

    def test_create_new_field(self):
        model = self.env['ir.model'].search([('model', '=', 'res.partner')])
        self.studio_controller.create_new_field({
            'model_name': model.model,
            'name': 'x_test_create_ai',
            'type': 'char',
            'ai': True,
            'system_prompt': "<p>Hi</p>",
        })
        field = self.env['ir.model.fields'].with_context(studio=True).search([('name', '=', 'x_test_create_ai'), ('model', '=', model.model)])
        self.assertTrue(field.ai)
        self.assertEqual(field.system_prompt, "<p>Hi</p>")
