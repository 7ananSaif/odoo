from odoo.tests.common import TransactionCase, new_test_user


class TestVoipCall(TransactionCase):
    def test_is_within_same_company_true_with_contacts_of_same_company(self):
        caller = new_test_user(self.env, login="test_user")
        company = self.env["res.partner"].create(
            {
                "name": "Test Company",
                "is_company": True,
            },
        )
        caller_partner = self.env["res.partner"].create(
            {
                "name": "Contact 1",
                "parent_id": company.id,
            },
        )
        callee_partner = self.env["res.partner"].create(
            {
                "name": "Contact 2",
                "parent_id": company.id,
            },
        )
        self.assertEqual(caller_partner.commercial_partner_id, company)
        self.assertEqual(callee_partner.commercial_partner_id, company)
        caller.partner_id = caller_partner
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "partner_id": callee_partner.id,
                "user_id": caller.id,
            },
        )
        self.assertTrue(call.is_within_same_company)

    def test_is_within_same_company_false_with_contacts_of_different_companies(self):
        caller = new_test_user(self.env, login="test_user")
        company_1 = self.env["res.partner"].create(
            {
                "name": "Test Company 1",
                "is_company": True,
            },
        )
        company_2 = self.env["res.partner"].create(
            {
                "name": "Test Company 2",
                "is_company": True,
            },
        )
        caller_partner = self.env["res.partner"].create(
            {
                "name": "Contact 1",
                "parent_id": company_1.id,
            },
        )
        callee_partner = self.env["res.partner"].create(
            {
                "name": "Contact 2",
                "parent_id": company_2.id,
            },
        )
        self.assertEqual(caller_partner.commercial_partner_id, company_1)
        self.assertEqual(callee_partner.commercial_partner_id, company_2)
        caller.partner_id = caller_partner
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "partner_id": callee_partner.id,
                "user_id": caller.id,
            },
        )
        self.assertFalse(call.is_within_same_company)

    def test_is_within_same_company_false_no_partner(self):
        caller = new_test_user(self.env, login="test_user")
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "user_id": caller.id,
            },
        )
        self.assertFalse(call.is_within_same_company)

    def test_is_within_same_company_false_user_no_partner(self):
        company = self.env["res.partner"].create(
            {
                "name": "Test Company",
                "is_company": True,
            },
        )
        caller = new_test_user(self.env, login="test_user")
        callee_partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "partner@example.com",
            },
        )
        callee_partner.commercial_partner_id = company
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "partner_id": callee_partner.id,
                "user_id": caller.id,
            },
        )
        self.assertFalse(call.is_within_same_company)

    def test_get_contact_info_with_voip_extension(self):
        user_with_extension = new_test_user(self.env, login="user_with_extension", voip_username="8888")
        voip_user = new_test_user(self.env, login="voip_user")
        call = self.env["voip.call"].create(
            {
                "phone_number": "8888",
                "user_id": voip_user.id,
            }
        )
        store_data = call.with_user(voip_user).get_contact_info()

        self.assertEqual(store_data["res.partner"][0]["id"], user_with_extension.partner_id.id)
