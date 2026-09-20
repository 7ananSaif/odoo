import base64

from odoo import Command
from odoo.addons.sale.tests.common import SaleCommon

from .common_exports import StudioExportCase, StudioExportSerializer


class TestStudioExports(StudioExportCase):
    def test_export_customizations(self):
        custom_model = self.create_customization(
            "ir.model", name="Furnace Types", model="x_furnace_types"
        )
        custom_field = self.create_customization(
            "ir.model.fields",
            name="x_studio_max_temp",
            ttype="integer",
            model_id=custom_model.id,
        )
        custom_view = self.create_customization(
            "ir.ui.view",
            name="Kanban view for x_furnace_types",
            model="x_furnace_types",
            type="kanban",
            arch="""
                <kanban>
                    <templates>
                        <t t-name="card">
                            <field name="x_studio_max_temp" />
                        </t>
                    </templates>
                </kanban>
            """,
        )
        custom_action = self.create_customization(
            "ir.actions.act_window",
            name="Furnaces",
            res_model="x_furnace_types",
            view_mode="list,form,kanban",
            help="<p>This is your new action.</p>",
        )
        custom_menu_1 = self.create_customization(
            "ir.ui.menu",
            name="My Furnaces",
        )
        custom_menu_2 = self.create_customization(
            "ir.ui.menu",
            name="Furnaces Types",
            parent_id=custom_menu_1.id,
            action=f"ir.actions.act_window,{custom_action.id}",
        )

        # Create a record to show that it is not exported
        # (appears neither in manifest nor in filelist)
        self.env[custom_model.model].create(
            {"x_name": "Austenitization", "x_studio_max_temp": 1200}
        )

        self.studio_export()
        self.assertManifest(
            data=[
                "data/ir_model.xml",
                "data/ir_model_fields.xml",
                "data/ir_ui_view.xml",
                "data/ir_actions_act_window.xml",
                "data/ir_ui_menu.xml",
            ],
            depends=["web_studio"],
        )
        self.assertFileList(
            "data/ir_model.xml",
            "data/ir_model_fields.xml",
            "data/ir_ui_view.xml",
            "data/ir_actions_act_window.xml",
            "data/ir_ui_menu.xml",
        )
        self.assertXML(
            "data/ir_model.xml",
            f"""<odoo>
            <record id="{self.get_xmlid(custom_model)}" model="ir.model" context="{{'studio': True}}">
                <field name="info"><![CDATA[{custom_model.info}]]></field>
                <field name="model">x_furnace_types</field>
                <field name="name">Furnace Types</field>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "data/ir_model_fields.xml",
            f"""<odoo>
            <record id="{self.get_xmlid(custom_field)}" model="ir.model.fields" context="{{'studio': True}}">
                <field name="ttype">integer</field>
                <field name="copied" eval="True"/>
                <field name="field_description">X Studio Max Temp</field>
                <field name="model">x_furnace_types</field>
                <field name="model_id" ref="{self.get_xmlid(custom_model)}"/>
                <field name="name">x_studio_max_temp</field>
                <field name="on_delete" eval="False"/>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "data/ir_ui_view.xml",
            f"""<odoo>
            <record id="{self.get_xmlid(custom_view)}" model="ir.ui.view" context="{{'studio': True}}">
                <field name="arch" type="xml">
                        <kanban>
                            <templates>
                                <t t-name="card">
                                    <field name="x_studio_max_temp" />
                                </t>
                            </templates>
                        </kanban>
                </field>
                <field name="model">x_furnace_types</field>
                <field name="name">Kanban view for x_furnace_types</field>
                <field name="type">kanban</field>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "data/ir_actions_act_window.xml",
            f"""<odoo>
            <record id="{self.get_xmlid(custom_action)}" model="ir.actions.act_window" context="{{'studio': True}}">
                <field name="help"><![CDATA[<p>This is your new action.</p>]]></field>
                <field name="name">Furnaces</field>
                <field name="res_model">x_furnace_types</field>
                <field name="view_mode">list,form,kanban</field>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "data/ir_ui_menu.xml",
            f"""<odoo>
            <record id="{self.get_xmlid(custom_menu_1)}" model="ir.ui.menu" context="{{'studio': True}}">
                <field name="name">My Furnaces</field>
            </record>
            <record id="{self.get_xmlid(custom_menu_2)}" model="ir.ui.menu" context="{{'studio': True}}">
                <field name="action" ref="{self.get_xmlid(custom_action)}" />
                <field name="name">Furnaces Types</field>
                <field name="parent_id" ref="{self.get_xmlid(custom_menu_1)}" />
            </record>
            </odoo>""",
        )

    def test_export_customizations_without_export_model(self):
        custom_model = self.create_customization(
            "ir.model", name="Furnace Types", model="x_furnace_types"
        )
        self.create_customization(
            "ir.model.fields",
            name="x_studio_max_temp",
            ttype="integer",
            model_id=custom_model.id,
        )
        CustomModel = self.env[custom_model.model].with_user(2).sudo()
        CustomModel.create({"x_name": "Austenitization", "x_studio_max_temp": 1200})

        # Without export model, the custom model data are not exported
        self.studio_export()
        self.assertFileList("data/ir_model.xml", "data/ir_model_fields.xml")

    def test_export_customizations_with_export_model(self):
        custom_model = self.create_customization(
            "ir.model", name="Furnace Types", model="x_furnace_types"
        )
        self.create_customization(
            "ir.model.fields",
            name="x_studio_max_temp",
            ttype="integer",
            model_id=custom_model.id,
        )
        CustomModel = self.env[custom_model.model].with_user(2).sudo()
        furnace_type = CustomModel.create(
            {"x_name": "Austenitization", "x_studio_max_temp": 1200}
        )

        # With the export model, the custom model data is exported
        self.create_export_model(CustomModel._name)
        self.studio_export()
        self.assertFileList(
            "data/ir_model.xml",
            "data/ir_model_fields.xml",
            "data/x_furnace_types.xml",
        )
        self.assertXML(
            "data/x_furnace_types.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(furnace_type)}" model="x_furnace_types">
                <field name="x_studio_max_temp">1200</field>
                <field name="x_name">Austenitization</field>
            </record>
            </odoo>""",
        )

    def test_simple_export_model_without_record(self):
        self.create_export_model(self.TestModel._name)

        # Without record, the export_model has no effect
        self.studio_export()
        self.assertFileList()

    def test_simple_export_model_with_record(self):
        self.create_export_model(self.TestModel._name)
        some_record = self.TestModel.create({"name": "Some record"})

        # Simple case
        self.studio_export()
        self.assertFileList("data/test_studio_export_model1.xml")
        self.assertXML("data/test_studio_export_model1.xml", f"""
            <odoo noupdate="1">
                <record id="{self.get_xmlid(some_record)}" model="test.studio_export.model1">
                    <field name="name">Some record</field>
                </record>
            </odoo>
        """)

    def test_simple_export_model_with_record_updatable(self):
        self.create_export_model(self.TestModel._name, updatable=True)
        some_record = self.TestModel.create({"name": "Some record"})

        # Without updatable mode
        self.studio_export()
        self.assertFileList("data/test_studio_export_model1.xml")
        self.assertXML("data/test_studio_export_model1.xml", f"""
            <odoo>
                <record id="{self.get_xmlid(some_record)}" model="test.studio_export.model1">
                    <field name="name">Some record</field>
                </record>
            </odoo>
        """)

    def test_simple_export_model_with_record_as_demo(self):
        self.create_export_model(self.TestModel._name, is_demo_data=True)
        some_record = self.TestModel.create({"name": "Some record"})

        # With is_demo_data mode, with updatable
        self.studio_export()
        self.assertFileList("demo/test_studio_export_model1.xml")
        self.assertXML("demo/test_studio_export_model1.xml", f"""
            <odoo noupdate="1">
                <record id="{self.get_xmlid(some_record)}" model="test.studio_export.model1">
                    <field name="name">Some record</field>
                </record>
            </odoo>
        """)

    def test_simple_export_model_with_record_as_demo_updatable(self):
        self.create_export_model(self.TestModel._name, updatable=True, is_demo_data=True)
        some_record = self.TestModel.create({"name": "Some record"})

        # With is_demo_data mode, without updatable
        self.studio_export()
        self.assertFileList("demo/test_studio_export_model1.xml")
        self.assertXML("demo/test_studio_export_model1.xml", f"""
            <odoo>
                <record id="{self.get_xmlid(some_record)}" model="test.studio_export.model1">
                    <field name="name">Some record</field>
                </record>
            </odoo>
        """)

    def test_export_model_with_demo_data(self):
        some_record = self.TestModel.create({"name": "Some record"})
        other_record = self.TestModel.create({"name": "Some other record"})
        self.create_export_model(self.TestModel._name, is_demo_data=True)
        self.studio_export()
        self.assertFileList("demo/test_studio_export_model1.xml")
        self.assertXML(
            "demo/test_studio_export_model1.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(some_record)}" model="test.studio_export.model1">
                <field name="name">Some record</field>
            </record>
            <record id="{self.get_xmlid(other_record)}" model="test.studio_export.model1">
                <field name="name">Some other record</field>
            </record>
            </odoo>""",
        )

    def test_export_model_with_binary_field_without_include_attachment(self):
        some_record = self.TestModel.create(
            {
                "name": "Some record",
                "binary_data": base64.b64encode(b"My binary attachment"),
            }
        )
        self.create_export_model(self.TestModel._name)

        # Without include_attachment
        self.studio_export()
        self.assertFileList(
            "data/test_studio_export_model1.xml",
            f"static/src/binary/test_studio_export_model1/{some_record.id}-binary_data",
        )
        self.assertXML(
            "data/test_studio_export_model1.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(some_record)}" model="test.studio_export.model1">
                <field name="name">Some record</field>
                <field name="binary_data" type="base64" file="studio_customization/static/src/binary/test_studio_export_model1/{some_record.id}-binary_data"/>
            </record>
            </odoo>""",
        )

    def test_export_model_with_binary_field_with_include_attachment(self):
        some_record = self.TestModel.create(
            {
                "name": "Some record",
                "binary_data": base64.b64encode(b"My binary attachment"),
            }
        )
        self.create_export_model(self.TestModel._name, include_attachment=True)

        # With include_attachment we have the same export result
        self.studio_export()
        self.assertFileList(
            "data/test_studio_export_model1.xml",
            f"static/src/binary/test_studio_export_model1/{some_record.id}-binary_data",
        )
        self.assertXML(
            "data/test_studio_export_model1.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(some_record)}" model="test.studio_export.model1">
                <field name="name">Some record</field>
                <field name="binary_data" type="base64" file="studio_customization/static/src/binary/test_studio_export_model1/{some_record.id}-binary_data"/>
            </record>
            </odoo>""",
        )

    def test_export_model_non_attachment_binary_field(self):
        self.create_customization(
            "ir.model.fields",
            name="x_test_binary",
            ttype="binary",
            model_id=self.env["ir.model"]._get("res.partner").id,
            state="manual",
            depends="name",
            compute="for partner in self: partner['x_test_binary'] = [{'key': 'value'}]",
            field_description="Test Binary Field",
            store=False,
        )
        partner = self.env["res.partner"].create({
            "name": "Test Partner Binary Field",
        })
        self.assertEqual(partner.x_test_binary, [{'key': 'value'}])
        wizard_data = self.env["studio.export.wizard.data"].create(
            [{"model": partner._name, "res_id": partner.id}]
        )
        wizard = self.env["studio.export.wizard"].create({
            "default_export_data": [Command.set(wizard_data.ids)],
        })
        export_info = wizard.get_export_info()
        studio_module = self.env["ir.module.module"].get_studio_module()
        self.exporter = StudioExportSerializer(self.env, studio_module, export_info)
        self._export_cache = {}
        self._export_iter = iter(self.exporter.serialize())
        self.assertFileContains(
            f"static/src/binary/res_partner/{partner.id}-x_test_binary",
            "[{'key': 'value'}]"
        )

    def test_export_model_with_many2one_attachment(self):
        some_record = self.TestModel.create({"name": "Some record"})
        attachment = self.env["ir.attachment"].create(
            {
                "name": "Some attachment",
                "datas": base64.b64encode(b"My attachment"),
                "res_model": self.TestModel._name,
                "res_id": some_record.id,
                "res_field": "attachment_id",
            }
        )
        some_record.attachment_id = attachment
        self.create_export_model(self.TestModel._name, include_attachment=True)
        self.studio_export()
        self.assertFileList(
            "data/test_studio_export_model1.xml",
            "data/ir_attachment_pre.xml",
            f"static/src/binary/ir_attachment/{attachment.id}-Someattachment",
        )
        self.assertManifest(
            depends=["test_web_studio"],
            data=["data/ir_attachment_pre.xml", "data/test_studio_export_model1.xml"],
        )
        self.assertXML(
            "data/ir_attachment_pre.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(attachment)}" model="ir.attachment">
                <field name="name">Some attachment</field>
                <field name="datas" type="base64" file="studio_customization/static/src/binary/ir_attachment/{attachment.id}-Someattachment"/>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "data/test_studio_export_model1.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(some_record)}" model="test.studio_export.model1">
                <field name="name">Some record</field>
                <field name="attachment_id" ref="{self.get_xmlid(attachment)}"/>
            </record>
            </odoo>""",
        )

    def test_export_model_with_one2many_attachment(self):
        some_record = self.TestModel.create({"name": "Some record"})
        attachment1 = self.env["ir.attachment"].create(
            {
                "name": "Some attachment",
                "datas": base64.b64encode(b"My attachment"),
                "res_model": self.TestModel._name,
                "res_id": some_record.id,
                "res_field": "attachment_ids",
            }
        )
        attachment2 = self.env["ir.attachment"].create(
            {
                "name": "Another attachment",
                "datas": base64.b64encode(b"My second attachment"),
                "res_model": self.TestModel._name,
                "res_id": some_record.id,
                "res_field": "attachment_ids",
            }
        )
        some_record.attachment_ids = [Command.set([attachment1.id, attachment2.id])]
        self.create_export_model(self.TestModel._name, include_attachment=True)
        self.studio_export()
        self.assertFileList(
            "data/test_studio_export_model1.xml",
            "data/ir_attachment_post.xml",
            f"static/src/binary/ir_attachment/{attachment1.id}-Someattachment",
            f"static/src/binary/ir_attachment/{attachment2.id}-Anotherattachment",
        )
        self.assertManifest(
            depends=["test_web_studio"],
            data=["data/test_studio_export_model1.xml", "data/ir_attachment_post.xml"],
        )
        self.assertXML(
            "data/ir_attachment_post.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(attachment2)}" model="ir.attachment">
                <field name="name">Another attachment</field>
                <field name="datas" type="base64" file="studio_customization/static/src/binary/ir_attachment/{attachment2.id}-Anotherattachment" />
                <field name="res_id" ref="{self.get_xmlid(some_record)}" />
                <field name="res_model">test.studio_export.model1</field>
                <field name="res_field">attachment_ids</field>
            </record>
            <record id="{self.get_xmlid(attachment1)}" model="ir.attachment">
                <field name="name">Some attachment</field>
                <field name="datas" type="base64" file="studio_customization/static/src/binary/ir_attachment/{attachment1.id}-Someattachment" />
                <field name="res_id" ref="{self.get_xmlid(some_record)}" />
                <field name="res_model">test.studio_export.model1</field>
                <field name="res_field">attachment_ids</field>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "data/test_studio_export_model1.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(some_record)}" model="test.studio_export.model1">
                <field name="name">Some record</field>
            </record>
            </odoo>""",
        )

    def test_empty_models_and_fields(self):
        # Test that models without records do not export any data
        # and empty fields are not exported

        model2_record1 = self.TestModel2.create({
            "name": "Some Record"
        })
        model2_record2 = self.TestModel2.create({
            "name": "",
            "model2_id": model2_record1.id
        })

        self.create_export_model(self.TestModel2._name)
        self.create_export_model(self.TestModel3._name)

        self.studio_export()
        self.assertManifest(
            data=[
                "data/test_studio_export_model2.xml",
            ],
        )
        self.assertFileList(
            "data/test_studio_export_model2.xml",
        )

        self.assertXML(
            "data/test_studio_export_model2.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(model2_record1)}" model="test.studio_export.model2">
                <field name="name">Some Record</field>
            </record>
            <record id="{self.get_xmlid(model2_record2)}" model="test.studio_export.model2">
                <field name="model2_id" ref="{self.get_xmlid(model2_record1)}"/>
            </record>
            </odoo>""",
        )

    def test_export_data_related_to_demo(self):
        # Test that master data (non demo) does not export fields related
        # to demo records, but data records related to demo are also exported
        # as demo with only the fields related to said demo records.

        model3_record = self.TestModel3.create({"name": "Some record"})
        model2_record = self.TestModel2.create({
            "name": "Some other record",
            "model3_id": model3_record.id
        })

        self.create_export_model(self.TestModel2._name, is_demo_data=False)
        self.create_export_model(self.TestModel3._name, is_demo_data=True)

        self.studio_export()
        self.assertFileList(
            "data/test_studio_export_model2.xml",
            "demo/test_studio_export_model2.xml",
            "demo/test_studio_export_model3.xml",
        )
        self.assertXML(
            "data/test_studio_export_model2.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(model2_record)}" model="test.studio_export.model2">
                <field name="name">Some other record</field>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "demo/test_studio_export_model3.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(model3_record)}" model="test.studio_export.model3">
                <field name="name">Some record</field>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "demo/test_studio_export_model2.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(model2_record)}" model="test.studio_export.model2">
                <field name="model3_id" ref="{self.get_xmlid(model3_record)}"/>
            </record>
            </odoo>""",
        )

    def test_export_dependencies_order(self):
        # Test that files and records order respects dependencies

        model3_record = self.TestModel3.create({"name": "Some record"})
        model2_record = self.TestModel2.create({
            "name": "Some other record",
            "model3_id": model3_record.id
        })
        model2b_record = self.TestModel2.create({
            "name": "Some other record",
            "model2_id": model2_record.id,
            "model3_id": model3_record.id
        })
        model2c_record = self.TestModel2.create({"name": "Yet another record"})
        model2_record.write({
            "res_model": self.TestModel2._name,
            "res_id": model2c_record.id,
        })

        self.create_export_model(self.TestModel2._name)
        self.create_export_model(self.TestModel3._name)

        self.studio_export()
        self.assertManifest(
            data=[
                "data/test_studio_export_model3.xml",
                "data/test_studio_export_model2.xml",
            ],
        )
        self.assertFileList(
            "data/test_studio_export_model3.xml",
            "data/test_studio_export_model2.xml",
        )
        self.assertXML(
            "data/test_studio_export_model3.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(model3_record)}" model="test.studio_export.model3">
                <field name="name">Some record</field>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "data/test_studio_export_model2.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(model2c_record)}" model="test.studio_export.model2">
                <field name="name">Yet another record</field>
            </record>
            <record id="{self.get_xmlid(model2_record)}" model="test.studio_export.model2">
                <field name="name">Some other record</field>
                <field name="model3_id" ref="{self.get_xmlid(model3_record)}"/>
                <field name="res_model">test.studio_export.model2</field>
                <field name="res_id" ref="{self.get_xmlid(model2c_record)}"/>
            </record>
            <record id="{self.get_xmlid(model2b_record)}" model="test.studio_export.model2">
                <field name="name">Some other record</field>
                <field name="model2_id" ref="{self.get_xmlid(model2_record)}"/>
                <field name="model3_id" ref="{self.get_xmlid(model3_record)}"/>
            </record>
            </odoo>""",
        )

    def test_export_handles_circular_dependencies(self):
        # Test that models circular dependencies appear in warning.txt
        # and only if some records causes it
        model3_record = self.TestModel3.create({
            "name": "Record 3",
        })
        model2_record = self.TestModel2.create({
            "name": "Record 2",
            "model3_id": model3_record.id
        })
        model1_record = self.TestModel.create({
            "name": "Record 1",
            "model2_id": model2_record.id
        })
        model3_record.update({"model1_id": model1_record.id})

        self.create_export_model(self.TestModel._name)
        self.create_export_model(self.TestModel2._name)
        self.create_export_model(self.TestModel3._name)

        self.studio_export()
        self.assertFileList(
            "warnings.txt",
            "data/test_studio_export_model1.xml",
            "data/test_studio_export_model2.xml",
            "data/test_studio_export_model3.xml",
        )

        self.assertXML(
            "data/test_studio_export_model1.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(model1_record)}" model="test.studio_export.model1">
                <field name="name">Record 1</field>
                <field name="model2_id" ref="{self.get_xmlid(model2_record)}"/>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "data/test_studio_export_model2.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(model2_record)}" model="test.studio_export.model2">
                <field name="name">Record 2</field>
                <field name="model3_id" ref="{self.get_xmlid(model3_record)}"/>
            </record>
            </odoo>""",
        )
        self.assertXML(
            "data/test_studio_export_model3.xml",
            f"""<odoo noupdate="1">
            <record id="{self.get_xmlid(model3_record)}" model="test.studio_export.model3">
                <field name="name">Record 3</field>
                <field name="model1_id" ref="{self.get_xmlid(model1_record)}"/>
            </record>
            </odoo>""",
        )

        self.assertFileContains(
            "warnings.txt",
            f"""Found 1 circular dependencies (you may have to change data loading order to avoid issues when importing):
(data) {self.TestModel._name} -> {self.TestModel2._name} -> {self.TestModel3._name} -> {self.TestModel._name}
""",
        )

    def test_export_abstract_actions_with_proper_types(self):
        WindowActions = self.env["ir.actions.act_window"].with_user(2)
        window_action = WindowActions.create({
            "name": "Test action",
            "type": "ir.actions.act_window",
            "res_model": self.TestModel._name,
            "view_mode": "form",
            "target": "new",
        })

        URLActions = self.env["ir.actions.act_url"].with_user(2)
        url_action = URLActions.create({
            "name": "Test action",
            "type": "ir.actions.act_url",
            "url": "http://odoo.com",
        })

        self.create_export_model("ir.actions.actions", domain=[("id", "in", [window_action.id, url_action.id])])
        self.studio_export()

        self.assertFileList(
            "data/ir_actions_act_window.xml",
            "data/ir_actions_act_url.xml",
        )

        self.assertXML(
            "data/ir_actions_act_window.xml",
            f"""<odoo>
            <record id="{self.get_xmlid(window_action)}" model="ir.actions.act_window">
                <field name="name">Test action</field>
                <field name="res_model">{self.TestModel._name}</field>
                <field name="view_mode">form</field>
                <field name="target">new</field>
            </record>
            </odoo>""",
        )

        self.assertXML(
            "data/ir_actions_act_url.xml",
            f"""<odoo>
            <record id="{self.get_xmlid(url_action)}" model="ir.actions.act_url">
                <field name="name">Test action</field>
                <field name="display_name">Test action</field>
                <field name="url"><![CDATA[http://odoo.com]]></field>
            </record>
            </odoo>""",
        )


class TestSpecificStudioExports_SaleOrder(
    SaleCommon,
    StudioExportCase
):
    def test_export_demo_sale_orders(self):
        # SPECIFIC: Confirm demo sale orders
        self.sale_order.action_confirm()
        self.create_export_model("sale.order", domain=[("id", "in", [self.sale_order.id])], is_demo_data=True)
        self.create_export_model("sale.order.line", domain=[("order_id", "in", [self.sale_order.id])], is_demo_data=True)
        self.studio_export()
        self.assertFileList(
            "demo/sale_order.xml",
            "demo/sale_order_line.xml",
            "demo/sale_order_confirm.xml",
            "warnings.txt",  # because no products nor partners are exported here, but that's not the point of this test.
        )
        evl_attr_value = f"[[ref('{self.get_xmlid(self.sale_order)}')]]"
        self.assertXML(
            "demo/sale_order_confirm.xml",
            f"""<odoo>
                <!--Update sale order stages-->
                <function model="sale.order" name="action_confirm" eval="{evl_attr_value}"/>
            </odoo>""",
        )


class TestSpecificStudioExports_Website(StudioExportCase):
    def test_unlink_default_main_menu(self):
        # SPECIFIC: unlink the default main menu from the website if needed
        website = self.env['website'].get_current_website()
        menus = self.env['website.menu'].search([('website_id', '=', website.id)])
        self.create_export_model("website.menu", domain=[("id", "in", [m.id for m in menus])])
        self.studio_export()
        if self.get_xmlid(website) != "website.default_website" or not any(r['url'] == '/default-main-menu' for r in menus):
            # Only written for the default website and on a fresh install
            self.skipTest("This test is only written for the default website and on a fresh install")

        self.assertFileList(
            "warnings.txt",  # because we do not export all the necessary data for website exports, but that's not the point of this test
            "data/website_menu.xml",
        )

        # should have only function to unlink the default main menu
        nodes = self.get_xml_nodes("data/website_menu.xml", "/odoo/*")
        self.assertEqual(len(nodes), 1 + len(menus), "has a child for each menu + 1")
        self.assertEqual([n.tag for n in nodes], ["function"] + ["record"] * len(menus))
        self.assertXML(
            nodes[0],
            """<function model="website.menu" name="unlink">
                <value model="website.menu" eval="obj().search([('website_id', '=', ref('website.default_website')), ('url', '=', '/default-main-menu')]).id"/>
            </function>""",
        )
