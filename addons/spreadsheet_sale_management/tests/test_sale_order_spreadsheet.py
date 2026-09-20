# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo.tests import Form
from odoo.tests.common import new_test_user
from odoo.addons.spreadsheet_edition.tests.spreadsheet_test_case import SpreadsheetTestCase


class SaleOrderSpreadsheet(SpreadsheetTestCase):

    def test_sale_order_action_open(self):
        spreadsheet = self.env["sale.order.spreadsheet"].create({"name": "spreadsheet"})
        quotation_template = self.env["sale.order.template"].create({
            "name": "Test template",
            "spreadsheet_template_id": spreadsheet.id
        })
        sale_order = self.env["sale.order"].create({
            "partner_id": self.env.user.partner_id.id,
            "sale_order_template_id": quotation_template.id
        })
        self.assertFalse(sale_order.spreadsheet_ids)
        action = sale_order.action_open_sale_order_spreadsheet()
        self.assertEqual(action["tag"], "action_sale_order_spreadsheet")
        self.assertTrue(sale_order.spreadsheet_ids)
        self.assertEqual(sale_order.spreadsheet_ids.id, action["params"]["spreadsheet_id"])

    def test_sale_order_action_open_twice(self):
        spreadsheet = self.env["sale.order.spreadsheet"].create({"name": "spreadsheet"})
        quotation_template = self.env["sale.order.template"].create({
            "name": "Test template",
            "spreadsheet_template_id": spreadsheet.id
        })
        sale_order = self.env["sale.order"].create({
            "partner_id": self.env.user.partner_id.id,
            "sale_order_template_id": quotation_template.id
        })
        sale_order.action_open_sale_order_spreadsheet()
        spreadsheets = sale_order.spreadsheet_ids
        sale_order.action_open_sale_order_spreadsheet()
        self.assertEqual(sale_order.spreadsheet_ids, spreadsheets, "it should be the same spreadsheet")

    def test_get_selector_spreadsheet_models(self):
        user = new_test_user(self.env, login="Raoul")
        result = self.env["spreadsheet.mixin"].with_user(user).get_selector_spreadsheet_models()
        self.assertFalse(any(r["model"] == "sale.order.spreadsheet" for r in result))

        user.group_ids |= self.env.ref("sales_team.group_sale_salesman")
        result = self.env["spreadsheet.mixin"].with_user(user).get_selector_spreadsheet_models()
        self.assertTrue(any(r["model"] == "sale.order.spreadsheet" for r in result))

    def test_sale_order_spreadsheet_deleted_with_related_order(self):
        spreadsheet = self.env["sale.order.spreadsheet"].create({"name": "spreadsheet"})
        quotation_template = self.env["sale.order.template"].create({
            "name": "Test template",
            "spreadsheet_template_id": spreadsheet.id
        })
        sale_order = self.env["sale.order"].create({
            "partner_id": self.env.user.partner_id.id,
            "sale_order_template_id": quotation_template.id
        })
        sale_order.action_open_sale_order_spreadsheet()
        so_spreadsheet = sale_order.spreadsheet_ids
        sale_order.unlink()
        self.assertFalse(so_spreadsheet.exists(), "spreadsheet should be deleted with the related order")
        self.assertTrue(spreadsheet.exists(), "Original spreadsheet should be unaltered")

    def test_copy_so_copies_spreadsheet_revision(self):
        spreadsheet = self.env["sale.order.spreadsheet"].create({"name": "spreadsheet"})
        quotation_template = self.env["sale.order.template"].create({
            "name": "Test template",
            "spreadsheet_template_id": spreadsheet.id
        })
        sale_order = self.env["sale.order"].create({
            "partner_id": self.env.user.partner_id.id,
            "sale_order_template_id": quotation_template.id
        })
        sale_order.action_open_sale_order_spreadsheet()

        so_spreadsheet = sale_order.spreadsheet_ids

        # dispatch a revision to the spreadsheet
        revision = self.new_revision_data(spreadsheet)
        spreadsheet.dispatch_spreadsheet_message(revision)

        new_so = sale_order.copy()
        new_so_spreadsheet = new_so.spreadsheet_ids

        self.assertEqual(
            so_spreadsheet.spreadsheet_revision_ids.commands,
            new_so_spreadsheet.spreadsheet_revision_ids.commands,
            "revision should be copied"
        )
        self.assertNotEqual(so_spreadsheet.id, new_so_spreadsheet.id, "spreadsheet id should be different")

    def test_access(self):
        salesman = new_test_user(self.env, login="Alice", groups="sales_team.group_sale_salesman")
        other_salesman = new_test_user(self.env, login="Bob", groups="sales_team.group_sale_salesman")
        template_spreadsheet = self.env["sale.order.spreadsheet"].create({"name": "spreadsheet"})
        quotation_template = self.env["sale.order.template"].create({
            "name": "Test template",
            "spreadsheet_template_id": template_spreadsheet.id
        })
        sale_order = self.env["sale.order"].with_user(salesman).create({
            "partner_id": self.env.user.partner_id.id,
            "sale_order_template_id": quotation_template.id,
            "user_id": salesman.id
        })
        sale_order.action_open_sale_order_spreadsheet()
        spreadsheet = sale_order.spreadsheet_id

        # user access for his own sale order
        self.assertTrue(sale_order.has_access("read"))
        self.assertTrue(sale_order.has_access("write"))
        self.assertFalse(sale_order.has_access("unlink"))
        self.assertTrue(spreadsheet.has_access("read"))
        self.assertTrue(spreadsheet.has_access("write"))
        self.assertTrue(spreadsheet.has_access("unlink"))

        # other users don't have access by default
        self.assertFalse(sale_order.with_user(other_salesman).has_access("read"))
        self.assertFalse(sale_order.with_user(other_salesman).has_access("write"))
        self.assertFalse(sale_order.with_user(other_salesman).has_access("unlink"))
        self.assertFalse(spreadsheet.with_user(other_salesman).has_access("read"))
        self.assertFalse(spreadsheet.with_user(other_salesman).has_access("write"))
        self.assertFalse(spreadsheet.with_user(other_salesman).has_access("unlink"))

        # add access to all orders
        other_salesman.group_ids |= self.env.ref("sales_team.group_sale_salesman_all_leads")
        self.assertTrue(sale_order.with_user(other_salesman).has_access("read"))
        self.assertTrue(sale_order.with_user(other_salesman).has_access("write"))
        self.assertFalse(sale_order.with_user(other_salesman).has_access("unlink"))
        self.assertTrue(spreadsheet.with_user(other_salesman).has_access("read"))
        self.assertTrue(spreadsheet.with_user(other_salesman).has_access("write"))
        self.assertTrue(spreadsheet.with_user(other_salesman).has_access("unlink"))

    def test_sale_order_template_change_after_open(self):
        """
        Test ensures that spreadsheet template is changed on changing sale order template,
        once spreadsheet has been opened.
        """
        # Ensure user has access to sale order templates
        self.env.user.group_ids += self.env.ref('sale_management.group_sale_order_template')
        spreadsheet = self.env["sale.order.spreadsheet"].create({"name": "spreadsheet"})
        spreadsheet2 = self.env["sale.order.spreadsheet"].create({"name": "spreadsheet2"})
        quotation_templates = self.env["sale.order.template"].create(
            [
                {"name": "Test template1", "spreadsheet_template_id": spreadsheet.id},
                {"name": "Test template2", "spreadsheet_template_id": spreadsheet2.id},
            ]
        )
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.env.user.partner_id.id,
                "sale_order_template_id": quotation_templates[0].id,
            }
        )
        self.assertFalse(sale_order.spreadsheet_ids)
        sale_order.action_open_sale_order_spreadsheet()
        so_spreadsheets = sale_order.spreadsheet_ids
        self.assertEqual(sale_order.spreadsheet_id.name, "spreadsheet")
        with Form(sale_order) as so:
            so.sale_order_template_id = quotation_templates[1]
            self.assertFalse(so.spreadsheet_id)
        self.assertFalse(so_spreadsheets.exists(), "previous spreadsheet should not exist")
        self.assertEqual(sale_order.sale_order_template_id.spreadsheet_template_id.name, "spreadsheet2")
