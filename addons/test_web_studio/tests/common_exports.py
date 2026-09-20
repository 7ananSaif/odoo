import ast
from itertools import starmap

from lxml import etree as ET
from odoo.fields import Command, Domain
from odoo.addons.web_studio.controllers.export_utils import StudioExportSerializer
from odoo.tests.common import TransactionCase, tagged

XMLPARSER = ET.XMLParser(remove_blank_text=True, strip_cdata=False, resolve_entities=False)


def nodes_equal(n1, n2):
    if n1.tag != n2.tag:
        return False
    if n1.text != n2.text:
        return False
    if n1.tail != n2.tail:
        return False
    if n1.attrib != n2.attrib:
        return False
    if len(n1) != len(n2):
        return False
    if n1.tag == "field":
        # compare a tostring version, to check if CDATA sections are preserved
        n1_str = ET.tostring(n1)
        n2_str = ET.tostring(n2)
        if n1_str != n2_str:
            return False
    if n1.tag == "record":
        # n1 and n2 children order doesn't matter, sort them by tagname, attrib['name']
        n1 = sorted(n1, key=lambda n: (n.tag, n.attrib.get("name")))
        n2 = sorted(n2, key=lambda n: (n.tag, n.attrib.get("name")))
    return all(starmap(nodes_equal, zip(n1, n2)))


@tagged("-at_install", "post_install")
class StudioExportCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self._customizations = []
        self._additional_models = self.env["studio.export.model"]
        self._additional_models.search([]).unlink()
        self.exporter = None
        self._export_iter = None
        self.TestModel = self.env["test.studio_export.model1"].with_user(2)
        self.TestModel2 = self.env["test.studio_export.model2"].with_user(2)
        self.TestModel3 = self.env["test.studio_export.model3"].with_user(2)

    def create_customization(self, _model, **kwargs):
        Model = self.env[_model].with_context(studio=True)
        custo = Model.create(kwargs)
        self._customizations.append(custo)
        return custo

    def create_export_model(self, _model, **kwargs):
        IrModel = self.env["ir.model"]
        vals = {"model_id": IrModel._get_id(_model)}
        vals.update(kwargs)
        export_model = self.env["studio.export.model"].create(vals)
        self._additional_models |= export_model
        self.addCleanup(export_model.unlink)
        return export_model

    def get_xml_nodes(self, filepath, xpath=None):
        root = self._get_exported(filepath)
        nodes = root.xpath(xpath) if xpath else root
        return [nodes] if not isinstance(nodes, list) else nodes

    def get_xmlid(self, record):
        return self.exporter.utils.get_xmlid(record)

    def studio_export(self):
        if self._export_iter:
            raise RuntimeError("Studio export already in progress: maybe make another test?")

        # Prepare the export wizard
        domain = Domain.OR(
            Domain("model", "=", custo._name) & Domain("res_id", "=", custo.id)
            for custo in self._customizations
        ) & Domain("studio", "=", True)
        custo_data = self.env["ir.model.data"].search(domain)
        custo_data = self.env["studio.export.wizard.data"].create(
            [
                {"model": d.model, "res_id": d.res_id, "studio": d.studio}
                for d in custo_data
            ]
        )
        wizard = self.env["studio.export.wizard"].create(
            {
                "default_export_data": [Command.set(custo_data.ids)],
                "additional_models": [Command.set(self._additional_models.ids)],
                "include_additional_data": True,
                "include_demo_data": True,
            }
        )
        export_info = wizard.get_export_info()

        # Start the export
        studio_module = self.env["ir.module.module"].get_studio_module()
        self.exporter = StudioExportSerializer(self.env, studio_module, export_info)
        self._export_cache = {}
        self._export_iter = iter(self.exporter.serialize())

    def xml_tostring(self, el):
        return ET.tostring(el, encoding="unicode", pretty_print=True)

    def _get_exported(self, name=None):
        if not self._export_iter:
            raise RuntimeError("No export has begun, use studio_export() first")
        while name not in self._export_cache:
            try:
                path, content = next(self._export_iter)
            except StopIteration:
                break
            if path.endswith(".xml"):
                self._export_cache[path] = ET.fromstring(content, parser=XMLPARSER)
            elif path.endswith("__manifest__.py"):
                self._export_cache[path] = ast.literal_eval(content.decode("utf-8"))
            else:
                self._export_cache[path] = content

        return self._export_cache[name] if name else self._export_cache

    def assertFileContains(self, path, content):
        file = self._get_exported(path)
        self.assertEqual(file, content)

    def assertFileList(self, *filenames):
        """You can omit __init__.py and __manifest__.py"""
        filenames += ("__init__.py", "__manifest__.py")
        exported = self._get_exported()
        self.assertEqual(set(exported.keys()), set(filenames))

    def assertManifest(self, **expected):
        exported = self._get_exported("__manifest__.py")
        for key, value in expected.items():
            if key == "depends":
                self.assertEqual(
                    self.exporter.utils.clean_dependencies(set(exported["depends"] + value)),
                    exported["depends"],
                )
            else:
                self.assertEqual(exported[key], value)

    def assertXML(self, actual, expected):
        actual = self.get_xml_nodes(actual)[0] if isinstance(actual, str) else actual
        expected = ET.fromstring(expected, parser=XMLPARSER) if isinstance(expected, str) else expected
        are_equal = nodes_equal(actual, expected)
        message = "Both XMLs are equal"
        if not are_equal:
            expected = self.xml_tostring(expected) if not isinstance(expected, str) else expected
            actual = self.xml_tostring(actual) if not isinstance(actual, str) else actual
            message = "\nExpected:\n%s\nActual:\n%s" % (expected, actual)
        self.assertTrue(are_equal, message)
