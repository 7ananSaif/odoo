# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import patch

from odoo import Command
from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.ai_fields.tools import UnresolvedQuery
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAiFieldsAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.admin, cls.internal = cls.env['res.users'].create([
            {
                'email': "admin_ai@example.com",
                'group_ids': [Command.link(cls.env.ref('base.group_user').id), Command.link(cls.env.ref('mail.group_mail_template_editor').id)],
                'login': "admin_ai",
                'name': "admin_ai",
            },
            {
                'login': 'internal_ai',
                'group_ids': [Command.link(cls.env.ref('base.group_user').id)],
                'name': 'internal_ai',
            },
        ])
        cls.parent = cls.env["test.ai.fields.parent"].create(
            {"properties_definition": [{"type": "char", "name": "char"}]})
        cls.record = cls.env["test.ai.fields.model"].create({"parent_id": cls.parent.id})

    def _mock_llm_api_get_token(self):
        def _mock_get_api_token(self):
            return "dummy"
        return patch.object(LLMApiService, '_get_api_token', _mock_get_api_token)

    def test_ai_field_access_properties(self):
        """Test that only the template editor can use expressions that are not in the allowed expressions list."""
        def _mocked_llm_api_request(self, method, endpoint, headers, body):
            return {'output': [{'type': 'message', 'content': [{'text': json.dumps({'value': 1337})}]}]}

        # allowed field
        self.record.with_user(self.internal).write({"properties": [{"type": "char", "name": "char", "definition_changed": True, "ai": True, "system_prompt": "This is my prompt <span data-ai-field='test_ai_fields'>test ai fields</span>"}]})

        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token():
            value = {"properties": [{"type": "char", "name": "char", "ai": True, "system_prompt": "This is my prompt}}", "value": "value"}]}
            self.assertEqual(self.record.with_user(self.internal).get_ai_property_value("properties.char", value), 1337)

        # not allowed field
        with self.assertRaises(AccessError):
            self.record.with_user(self.internal).write({"properties": [{"type": "char", "name": "char", "definition_changed": True, "ai": True, "system_prompt": "Bad prompt <span data-ai-field='parent_id.name'>parent name</span>"}]})
        self.record.with_user(self.admin).write({"properties": [{"type": "char", "name": "char", "definition_changed": True, "ai": True, "system_prompt": "Bad prompt <span data-ai-field='parent_id.name'>parent name</span>"}]})

        with self.assertRaises(AccessError):
            self.parent.with_user(self.internal).write({"properties_definition": [{"type": "char", "name": "char", "ai": True, "system_prompt": "Bad prompt <span data-ai-field='parent_id.name'>parent name</span>"}]})

        with self.assertRaises(AccessError):
            # Try to write forbidden expression on ai = False properties
            self.parent.with_user(self.internal).write({"properties_definition": [{"type": "char", "name": "char", "ai": False, "system_prompt": "Bad prompt <span data-ai-field='parent_id.name'>parent name</span>"}]})

        with self.assertRaises(AccessError):
            self.env["test.ai.fields.parent"].with_user(self.internal).create(
                {"properties_definition": [{"type": "char", "name": "char", "ai": True, "system_prompt": "Bad prompt <span data-ai-field='parent_id.name'>parent name</span>"}]})
        self.env["test.ai.fields.parent"].with_user(self.admin).create(
            {"properties_definition": [{"type": "char", "name": "char", "ai": True, "system_prompt": "Bad prompt <span data-ai-field='parent_id.name'>parent name</span>"}]})

        # Should allow `test_ai_fields` because it's whitelisted
        self.env["test.ai.fields.definition"].with_user(self.internal).create(
            {"properties_definition": [{"type": "char", "name": "char", "ai": True, "system_prompt": "Bad prompt <span data-ai-field='test_ai_fields'>test ai fields</span>"}]})

        # not allowed record
        no_access_record = self.env['test.ai.fields.model'].create({})
        rule = self.env['ir.rule'].create({
            'name': "private ai record",
            'model_id': self.env['ir.model']._get_id('test.ai.fields.model'),
            'domain_force': f"[('id', 'not in', {no_access_record.id})]"
        })
        with self.assertRaises(AccessError):
            self.record.with_user(self.internal).write({"properties": [{'type': 'many2one', 'name': 'many2one', 'definition_changed': True, 'ai': True, 'comodel': 'test.ai.fields.model', 'system_prompt': f'<p><span data-ai-record-id="{no_access_record.id}">msg</span></p>'}]})

        # allowed record
        rule.unlink()
        self.record.with_user(self.internal).write({"properties": [{'type': 'many2one', 'name': 'many2one', 'definition_changed': True, 'ai': True, 'comodel': 'test.ai.fields.model', 'system_prompt': f'<p><span data-ai-record-id="{no_access_record.id}">msg</span></p>'}]})

    def test_ai_fields_validation_many2one(self):
        def _mocked_llm_api_request(self, method, endpoint, headers, body):
            return {'output': [{'type': 'message', 'content': [{'text': json.dumps({'value': response})}]}]}

        records = self.env['res.partner'].create([{'name': f'partner {i}'} for i in range(4)])

        # Simulate that we removed the record we inserted in the prompt
        id_removed = self.env['res.partner'].search([], order="id DESC", limit=1).id + 1
        description = ['<span data-ai-record-id="%s">Description</span>' % r for r in (*records.ids[:3], id_removed)]

        system_prompt = 'This is my prompt 99 <span data-ai-field="name">name</span>}}. Choose between: ' + ' or '.join(description)

        self.record.write({"properties": [{
            "type": "many2one",
            "name": "many2one",
            "comodel": "res.partner",
            "definition_changed": True,
            "ai": True,
            "system_prompt": system_prompt,
        }]})
        self.env.flush_all()

        # Ensure that we don't parse the rendered prompt
        self.record.name = '<span data-ai-record-id="%s">Description</span>' % records[3].id

        response = records[0].id
        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token():
            self.assertEqual(self.record.get_ai_property_value("properties.many2one", None), {'id': records[0].id, 'display_name': records[0].display_name})

        # The record doesn't exist but is in the prompt
        response = id_removed
        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token():
            self.assertFalse(self.record.get_ai_property_value("properties.many2one", None))

        # The record exists but is not in the prompt
        response = records[3].id
        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token():
            self.assertFalse(self.record.get_ai_property_value("properties.many2one", None))

        # Test missing model
        self.record.write({"properties": [{
            "type": "many2one",
            "name": "many2one",
            # comodel is missing
            "definition_changed": True,
            "ai": True,
            "system_prompt": system_prompt,
        }]})
        self.env.flush_all()
        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token():
            self.assertFalse(self.record.get_ai_property_value("properties.many2one", None))

    def test_ai_fields_validation_many2many(self):
        def _mocked_llm_api_request(self, method, endpoint, headers, body):
            return {'output': [{'type': 'message', 'content': [{'text': json.dumps({'value': response})}]}]}

        records = self.env['res.partner'].create([{'name': f'partner {i}'} for i in range(5)])

        # Ensure that we don't parse the rendered prompt
        self.record.name = '<span data-ai-record-id="%s">Description</span>' % records[3].id

        # Simulate that we removed the record we inserted in the prompt
        id_removed = self.env['res.partner'].search([], order="id DESC", limit=1).id + 1
        description = ['<span data-ai-record-id="%s">Description</span>' % r for r in (*records.ids[:4], id_removed)]

        system_prompt = 'This is my prompt 99 <span data-ai-field="name">name</span>. Choose between: ' + ' or '.join(description)

        self.record.write({"properties": [{
            "type": "many2many",
            "name": "many2many",
            "comodel": "res.partner",
            "definition_changed": True,
            "ai": True,
            "system_prompt": system_prompt,
        }]})
        self.env.flush_all()

        # Ensure that we don't parse the rendered prompt
        self.record.name = '<span data-ai-record-id="%s">Description</span>' % records[3].id

        response = [records[0].id, id_removed, records[3].id, records[4].id]
        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token():
            self.assertEqual(
                self.record.get_ai_property_value("properties.many2many", None),
                [[records[0].id, records[0].display_name], [records[3].id, records[3].display_name]]
            )

        # Test missing model
        self.record.write({"properties": [{
            "type": "many2many",
            "name": "many2many",
            # comodel is missing
            "definition_changed": True,
            "ai": True,
            "system_prompt": system_prompt,
        }]})
        self.env.flush_all()
        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token():
            self.assertFalse(self.record.get_ai_property_value("properties.many2many", None))

    def test_ai_fields_validation_tags(self):
        def _mocked_llm_api_request(self, method, endpoint, headers, body):
            return {'output': [{'type': 'message', 'content': [{'text': json.dumps({'value': response})}]}]}

        system_prompt = 'This is my prompt 99 <t t-out="object.name"/>}}.'

        self.record.write({"properties": [{
            "type": "tags",
            "name": "tags",
            "definition_changed": True,
            "ai": True,
            "system_prompt": system_prompt,
            "tags": [["a", "A", 0], ["b", "B", 0], ["c", "C", 0], ["d", "D", 0]],
        }]})
        self.env.flush_all()

        response = "y,a,b,c,x"
        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token():
            self.assertEqual(self.record.get_ai_property_value("properties.tags", None), ["a", "b", "c"])

        # Test missing tags
        self.record.write({"properties": [{
            "type": "tags",
            "name": "tags",
            # tags is missing
            "definition_changed": True,
            "ai": True,
            "system_prompt": "Good prompt",
        }]})
        self.env.flush_all()
        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token(), self.assertRaises(UnresolvedQuery) as cm:
            self.record.get_ai_property_value("properties.tags", None)
        self.assertEqual(str(cm.exception), "No allowed values are provided in the prompt.")

    def test_get_ai_property_value_new_record(self):
        """Test `get_ai_property_value` when the record does not exist."""
        def _mocked_llm_api_request(self, method, endpoint, headers, body):
            return {'output': [{'type': 'message', 'content': [{'text': json.dumps({'value': f"response {body['input'][0]['content'][0]['text']}"})}]}]}

        values = {"properties": [{"type": "char", "name": "char", "ai": True, "system_prompt": 'This is my prompt <span data-ai-field="name">name</span>', "value": "value"}]}
        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token():
            # we just make sure no error is raised, as `get_ai_property_values` creates a new record (we don't have its id)
            self.env['test.ai.fields.model'].new().get_ai_property_value("properties.char", values)

    def test_ai_field_many2one_insert_first_records(self):
        """Test that we take the most used records."""
        valid_value_1, valid_value_2, invalid_value = self.env['res.partner'].create([
            # check if the name is added in the prompt
            {'name': 'valid <span data-ai-field="name">name</span>'},
            {'name': 'valid'},
            {'name': 'invalid'},
        ])

        self.env["ir.model.fields"].create({
            "name": "x_ai_many2one",
            "model_id": self.env["ir.model"]._get("test.ai.fields.model").id,
            "ttype": "many2one",
            "relation": "res.partner",
            "ai": True,
            "system_prompt": "System Prompt",
            "domain": [['id', '!=', invalid_value.id]],
        })
        self.record.name = "name added"  # should not be added in prompt

        result = self.record.ai_find_default_records("res.partner", [['id', '!=', invalid_value.id]], "x_ai_many2one")
        self.assertNotIn(invalid_value, result)
        self.assertIn(valid_value_1, result)
        self.assertIn(valid_value_2, result)

        # Check that the most used records are inserted
        self.env['ir.config_parameter'].sudo().set_param('ai_field.insert_x_first_records', '3')
        less_used = self.env['res.partner'].create([
            {'name': 'less used 1'},
            {'name': 'less used 2'},
            {'name': 'less used 3'},
        ])
        self.env['test.ai.fields.model'].create([
            {'x_ai_many2one': less_used[0].id},
            {'x_ai_many2one': less_used[1].id},
            {'x_ai_many2one': less_used[2].id},
        ])
        most_used_records = self.env['res.partner'].create([
            {'name': 'more used 1'},
            {'name': 'more used 2'},
            {'name': 'more used 3'},
        ])
        self.env['test.ai.fields.model'].create([
            {'x_ai_many2one': most_used_records[0].id},
            {'x_ai_many2one': most_used_records[1].id},
            {'x_ai_many2one': most_used_records[2].id},
        ] * 5)

        result = self.record.ai_find_default_records("res.partner", [['id', '!=', invalid_value.id]], "x_ai_many2one")
        for record in less_used:
            self.assertNotIn(record, result)
        for record in most_used_records:
            self.assertIn(record, result)

        # Now we increased the limit, it should take unused records
        self.env['ir.config_parameter'].sudo().set_param('ai_field.insert_x_first_records', '3000')

        result = self.record.ai_find_default_records("res.partner", [['id', '!=', invalid_value.id]], "x_ai_many2one")
        for record in less_used | most_used_records:
            self.assertIn(record, result)

    def test_ai_field_many2one_properties_insert_first_records(self):
        """Test that we take the most used records."""
        self.env['ir.config_parameter'].sudo().set_param('ai_field.insert_x_first_records', '3000')
        self.record.write({"properties": [{
            "type": "many2one",
            "name": "many2one",
            "comodel": "res.partner",
            "definition_changed": True,
            "ai": True,
            "system_prompt": 'This is my m2o prompt',
            "domain": [('name', '!=', 'invalid')],
        }]})
        self.env.flush_all()

        valid_partner, invalid_partner = self.env['res.partner'].create([
            {'name': 'valid'},
            {'name': 'invalid'},
        ])

        result = self.record.ai_find_default_records("res.partner", [('name', '!=', 'invalid')], "properties", "many2one")
        self.assertNotIn(invalid_partner, result)
        self.assertIn(valid_partner, result)

        self.env['ir.config_parameter'].sudo().set_param('ai_field.insert_x_first_records', '3')
        less_used = self.env['res.partner'].create([
            {'name': 'less used 1'},
            {'name': 'less used 2'},
            {'name': 'less used 3'},
        ])
        self.env['test.ai.fields.model'].create([
            {'parent_id': self.record.parent_id.id, 'properties': {'many2one': less_used[0].id}},
            {'parent_id': self.record.parent_id.id, 'properties': {'many2one': less_used[1].id}},
            {'parent_id': self.record.parent_id.id, 'properties': {'many2one': less_used[2].id}},
        ])
        most_used_records = self.env['res.partner'].create([
            {'name': 'more used 1'},
            {'name': 'more used 2'},
            {'name': 'more used 3'},
        ])
        self.env['test.ai.fields.model'].create([
            {'parent_id': self.record.parent_id.id, 'properties': {'many2one': most_used_records[0].id}},
            {'parent_id': self.record.parent_id.id, 'properties': {'many2one': most_used_records[1].id}},
            {'parent_id': self.record.parent_id.id, 'properties': {'many2one': most_used_records[2].id}},
        ] * 5)

        result = self.record.ai_find_default_records("res.partner", [('name', '!=', 'invalid')], "properties", "many2one")
        for record in less_used:
            self.assertNotIn(record, result)
        for record in most_used_records:
            self.assertIn(record, result)

        # If we increase the limit, use all records
        self.env['ir.config_parameter'].sudo().set_param('ai_field.insert_x_first_records', '3000')

        result = self.record.ai_find_default_records("res.partner", [('name', '!=', 'invalid')], "properties", "many2one")
        for record in less_used | most_used_records:
            self.assertIn(record, result)
