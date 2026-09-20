from odoo.tests import tagged

from odoo.addons.sales_team.tests.common import TestSalesCommon


@tagged("post_install", "-at_install")
class TestResPartner(TestSalesCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_no_opportunities = cls.env["res.partner"].create(
            {
                "name": "Mahmoud El-khatib",
                "phone": "+1234567890",
                "email": "no.opportunities@test.example.com",
            },
        )
        cls.partner_one_opportunity = cls.env["res.partner"].create(
            {
                "name": "Hany El-sharqawi",
                "phone": "+1234567891",
                "email": "one.opportunity@test.example.com",
            },
        )
        cls.partner_multiple_opportunities = cls.env["res.partner"].create(
            {
                "name": "Mina Ezzat",
                "phone": "+1234567892",
                "email": "multiple.opportunities@test.example.com",
            },
        )
        cls.opportunity_1 = cls.env["crm.lead"].create(
            {
                "name": "Test Opportunity 1",
                "type": "opportunity",
                "partner_id": cls.partner_one_opportunity.id,
                "user_id": cls.user_sales_manager.id,
                "probability": 50,
            },
        )
        cls.opportunity_2 = cls.env["crm.lead"].create(
            {
                "name": "Test Opportunity 2",
                "type": "opportunity",
                "partner_id": cls.partner_multiple_opportunities.id,
                "user_id": cls.user_sales_manager.id,
                "probability": 30,
            },
        )
        cls.opportunity_3 = cls.env["crm.lead"].create(
            {
                "name": "Test Opportunity 3",
                "type": "opportunity",
                "partner_id": cls.partner_multiple_opportunities.id,
                "user_id": cls.user_sales_salesman.id,
                "probability": 70,
            },
        )
        cls.call_no_partner = cls.env["voip.call"].create(
            {
                "phone_number": "+1234567899",
            },
        )
        cls.partner_no_opportunities.invalidate_recordset()
        cls.partner_one_opportunity.invalidate_recordset()
        cls.partner_multiple_opportunities.invalidate_recordset()

    def test_get_view_opportunities_action(self):
        allowed_methods = {
            "get_view_opportunities_action": lambda obj, **kwargs: obj.get_view_opportunities_action(**kwargs),
        }
        test_cases = [
            {
                "label": "no_opportunities",
                "input": self.partner_no_opportunities,
                "method": "get_view_opportunities_action",
                "args": {},
                "expected": {
                    "name": "Opportunities",
                    "res_model": "crm.lead",
                    "views": [[False, "form"]],
                    "res_id": False,
                    "context": {
                        "default_partner_id": self.partner_no_opportunities.id,
                    },
                    "opportunity_count": 0,
                },
            },
            {
                "label": "one_opportunity",
                "input": self.partner_one_opportunity,
                "method": "get_view_opportunities_action",
                "args": {},
                "expected": {
                    "name": "Opportunities",
                    "res_model": "crm.lead",
                    "views": [[False, "form"]],
                    "res_id": self.opportunity_1.id,
                    "opportunity_count": 1,
                },
            },
            {
                "label": "multiple_opportunities",
                "input": self.partner_multiple_opportunities,
                "method": "get_view_opportunities_action",
                "args": {},
                "expected": {
                    "name": "Opportunities",
                    "res_model": "crm.lead",
                    "views_not": [[False, "form"]],
                    "domain": self.partner_multiple_opportunities._get_contact_opportunities_domain(),
                    "opportunity_count": 2,
                },
            },
            {
                "label": "call_with_no_partner",
                "input": self.call_no_partner.partner_id,
                "method": "get_view_opportunities_action",
                "args": {"phone": self.call_no_partner.phone_number},
                "expected": {
                    "name": "Opportunities",
                    "res_model": "crm.lead",
                    "views": [[False, "form"]],
                    "context": {
                        "default_phone": self.call_no_partner.phone_number,
                    },
                },
            },
        ]
        for case in test_cases:
            with self.subTest(case=case["label"]):
                method_name = case["method"]
                if method_name not in allowed_methods:
                    raise ValueError(f"Method '{method_name}' is not allowed in tests")
                action = allowed_methods[method_name](case["input"], **case["args"])
                expected = case["expected"]
                for key, value in expected.items():
                    if key == "views_not":
                        self.assertNotEqual(action["views"], value)
                    elif key == "context":
                        for ctx_key, ctx_val in value.items():
                            self.assertEqual(action["context"][ctx_key], ctx_val)
                    elif key == "opportunity_count":
                        if hasattr(case["input"], "opportunity_count"):  # Only check if input is a partner
                            self.assertEqual(case["input"].opportunity_count, value)
                    elif key == "domain":
                        self.assertEqual(action["domain"], value)
                    else:
                        self.assertEqual(action[key], value)
