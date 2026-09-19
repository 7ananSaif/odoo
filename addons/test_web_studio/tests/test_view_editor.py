import json
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestViewEditor(HttpCase):

    def test_related_monetary_to_self(self):
        self.authenticate("admin", "admin")

        view = self.env["ir.ui.view"].create({
            "model": "test.studio.model_action",
            "type": "form",
            "arch": """<form><field name="display_name" /></form>"""
        })

        edit_view_params = dict(
            view_id=view.id,
            studio_view_arch="<data />",
            model="test.studio.model_action",
            operations=[
                {
                    "node": {
                        "field_description": {
                            "field_description": "New Related Field",
                            "name": "x_studio_related_field_for_test",
                            "type": "monetary",
                            "model_name": "test.studio.model_action",
                            "related": "monetary",
                            "readonly": True,
                            "copy": False,
                            "string": "Monetary",
                            "store": False,
                        },
                        "tag": "field",
                        "attrs": {}
                    },
                    "target": {
                        "tag": "field",
                        "attrs": {
                            "name": "display_name"
                        },
                        "xpath_info": [
                            {
                                "tag": "form",
                                "indice": 1
                            },
                            {
                                "tag": "field",
                                "indice": 1
                            }
                        ]
                    },
                    "position": "after",
                    "type": "add"
                }
            ]
        )

        self.url_open(
            "/web_studio/edit_view",
            data=json.dumps({"params": edit_view_params}),
            headers={"Content-Type": "application/json"}
        )

        new_field = self.env["ir.model.fields"]._get("test.studio.model_action", "x_studio_related_field_for_test")
        self.assertTrue(new_field.exists())
        self.assertEqual(new_field.related, "monetary")
        self.assertEqual(new_field.currency_field, "my_currency")

    def test_one2many_related(self):
        self.authenticate("admin", "admin")

        view = self.env["ir.ui.view"].create({
            "model": "test.studio.model_action",
            "type": "form",
            "arch": """<form><field name="display_name" /></form>"""
        })

        edit_view_params = dict(
            view_id=view.id,
            studio_view_arch="<data />",
            model="test.studio.model_action",
            operations=[
                {
                    "node": {
                        "field_description": {
                            "field_description": "New Related Field",
                            "name": "x_studio_related_field_for_test",
                            "type": "one2many",
                            "model_name": "test.studio.model_action",
                            "related": "partner_id.child_ids",
                            "readonly": True,
                            "copy": False,
                            "string": "Contact",
                            "store": False,
                            "relation": "res.partner",
                            "relational_model": "res.partner"
                        },
                        "tag": "field",
                        "attrs": {}
                    },
                    "target": {
                        "tag": "field",
                        "attrs": {
                            "name": "display_name"
                        },
                        "xpath_info": [
                            {
                                "tag": "form",
                                "indice": 1
                            },
                            {
                                "tag": "field",
                                "indice": 1
                            }
                        ]
                    },
                    "position": "after",
                    "type": "add"
                }
            ]
        )

        self.url_open(
            "/web_studio/edit_view",
            data=json.dumps({"params": edit_view_params}),
            headers={"Content-Type": "application/json"}
        )

        new_field = self.env["ir.model.fields"]._get("test.studio.model_action", "x_studio_related_field_for_test")
        self.assertTrue(new_field.exists())
        self.assertEqual(new_field.relation_field, False)

    def test_binary_related(self):
        self.authenticate("admin", "admin")

        view = self.env["ir.ui.view"].create({
            "model": "test.studio.model_action3",
            "type": "form",
            "arch": """<form><field name="display_name" /><field name="model_action_1_id" /></form>"""
        })

        edit_view_params = dict(
            view_id=view.id,
            studio_view_arch="<data />",
            model="test.studio.model_action3",
            operations=[
                {
                    "node": {
                        "field_description": {
                            "field_description": "New Related Field",
                            "name": "x_studio_related_field_for_test",
                            "type": "binary",
                            "model_name": "test.studio.model_action3",
                            "related": "model_action_1_id.custom_binary",
                            "readonly": True,
                            "copy": False,
                            "store": False,
                        },
                        "tag": "field",
                        "attrs": {}
                    },
                    "target": {
                        "tag": "field",
                        "attrs": {
                            "name": "display_name"
                        },
                        "xpath_info": [
                            {
                                "tag": "form",
                                "indice": 1
                            },
                            {
                                "tag": "field",
                                "indice": 1
                            }
                        ]
                    },
                    "position": "after",
                    "type": "add"
                }
            ]
        )

        self.url_open(
            "/web_studio/edit_view",
            data=json.dumps({"params": edit_view_params}),
            headers={"Content-Type": "application/json"}
        )

        self.assertEqual(self.env["ir.model.fields"]._get("test.studio.model_action3", "x_studio_related_field_for_test").related, "model_action_1_id.custom_binary")
        self.assertEqual(self.env["ir.model.fields"]._get("test.studio.model_action3", "x_studio_related_field_for_test_filename").related, "model_action_1_id.custom_binary_filename")
