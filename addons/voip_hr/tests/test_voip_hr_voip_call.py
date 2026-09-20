from odoo.fields import Command
from odoo.tests.common import TransactionCase, new_test_user


class TestVoipHrVoipCall(TransactionCase):
    def test_is_within_same_company_true_same_company_employees(self):
        company = self.env["res.company"].create({"name": "Company"})
        caller_partner = self.env["res.partner"].create({"name": "Caller", "email": "caller@example.com"})
        caller = new_test_user(self.env, login="user", company_id=company.id, partner_id=caller_partner.id)
        self.env["hr.employee"].create(
            {"name": "Caller Employee", "user_id": caller.id, "company_id": company.id},
        )
        callee_partner = self.env["res.partner"].create({"name": "Callee", "email": "callee@example.com"})
        callee_employee = self.env["hr.employee"].create({"name": "Callee Employee", "company_id": company.id})
        callee_partner.employee_ids = [Command.set([callee_employee.id])]
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "partner_id": callee_partner.id,
                "user_id": caller.id,
            },
        )

        self.assertTrue(call.is_within_same_company)

    def test_is_within_same_company_false_different_company_employees(self):
        company_1 = self.env["res.company"].create({"name": "Company 1"})
        company_2 = self.env["res.company"].create({"name": "Company 2"})
        caller_partner = self.env["res.partner"].create({"name": "Caller", "email": "caller@example.com"})
        caller = new_test_user(self.env, login="user", company_id=company_1.id, partner_id=caller_partner.id)
        self.env["hr.employee"].create({"name": "Caller Employee", "user_id": caller.id, "company_id": company_1.id})
        callee_partner = self.env["res.partner"].create({"name": "Callee", "email": "callee@example.com"})
        callee_employee = self.env["hr.employee"].create({"name": "Callee Employee", "company_id": company_2.id})
        callee_partner.employee_ids = [Command.set([callee_employee.id])]
        call = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_partner.id, "user_id": caller.id},
        )

        self.assertFalse(call.is_within_same_company)

    def test_is_within_same_company_multiple_employees_per_user(self):
        company_1 = self.env["res.company"].create({"name": "Company 1"})
        company_2 = self.env["res.company"].create({"name": "Company 2"})
        company_3 = self.env["res.company"].create({"name": "Company 3"})
        caller_partner = self.env["res.partner"].create({"name": "Caller", "email": "caller@example.com"})
        caller = new_test_user(self.env, login="user", company_id=company_1.id, partner_id=caller_partner.id)
        caller.company_ids = [Command.set([company_1.id, company_2.id, company_3.id])]
        self.env["hr.employee"].create({"name": "Caller Employee 1", "user_id": caller.id, "company_id": company_1.id})
        self.env["hr.employee"].create({"name": "Caller Employee 2", "user_id": caller.id, "company_id": company_2.id})
        callee_1_partner = self.env["res.partner"].create({"name": "Callee 1", "email": "callee@example.com"})
        callee_1_employee = self.env["hr.employee"].create({"name": "Callee 1 Employee", "company_id": company_1.id})
        callee_1_partner.employee_ids = [Command.set([callee_1_employee.id])]
        callee_2_partner = self.env["res.partner"].create({"name": "Callee 2", "email": "callee2@example.com"})
        callee_2_employee = self.env["hr.employee"].create({"name": "Callee 2 Employee", "company_id": company_2.id})
        callee_2_partner.employee_ids = [Command.set([callee_2_employee.id])]
        callee_3_partner = self.env["res.partner"].create({"name": "Callee 3", "email": "callee3@example.com"})
        callee_3_employee = self.env["hr.employee"].create({"name": "Callee 3 Employee", "company_id": company_3.id})
        callee_3_partner.employee_ids = [Command.set([callee_3_employee.id])]

        call_with_callee_1 = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_1_partner.id, "user_id": caller.id},
        )
        call_with_callee_2 = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_2_partner.id, "user_id": caller.id},
        )
        call_with_callee_3 = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_3_partner.id, "user_id": caller.id},
        )
        self.assertTrue(call_with_callee_1.is_within_same_company)
        self.assertTrue(call_with_callee_2.is_within_same_company)
        self.assertFalse(call_with_callee_3.is_within_same_company)

    def test_is_within_same_company_false_partner_no_employees(self):
        company = self.env["res.company"].create({"name": "Company"})
        caller_partner = self.env["res.partner"].create({"name": "Caller", "email": "caller@example.com"})
        caller = new_test_user(self.env, login="user", company_id=company.id, partner_id=caller_partner.id)
        self.env["hr.employee"].create({"name": "Caller Employee", "user_id": caller.id, "company_id": company.id})
        callee_partner = self.env["res.partner"].create({"name": "Callee", "email": "callee@example.com"})
        call = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_partner.id, "user_id": caller.id},
        )
        self.assertFalse(call.is_within_same_company)

    def test_is_within_same_company_false_user_no_employees(self):
        company = self.env["res.company"].create({"name": "Company"})
        caller_partner = self.env["res.partner"].create({"name": "Caller", "email": "caller@example.com"})
        caller = new_test_user(self.env, login="user", company_id=company.id, partner_id=caller_partner.id)
        callee_partner = self.env["res.partner"].create({"name": "Callee", "email": "callee@example.com"})
        callee_employee = self.env["hr.employee"].create({"name": "Callee Employee", "company_id": company.id})
        callee_partner.employee_ids = [Command.set([callee_employee.id])]
        call = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_partner.id, "user_id": caller.id},
        )
        self.assertFalse(call.is_within_same_company)

    def test_is_within_same_company_falls_back_to_base_logic(self):
        company_partner = self.env["res.partner"].create({"name": "Test Company", "is_company": True})
        caller = new_test_user(self.env, login="user")
        caller.partner_id.commercial_partner_id = company_partner
        callee_partner = self.env["res.partner"].create({"name": "Callee", "email": "callee@example.com"})
        callee_partner.commercial_partner_id = company_partner
        call = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_partner.id, "user_id": caller.id},
        )
        self.assertTrue(call.is_within_same_company)
