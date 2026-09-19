from odoo.tests import common, tagged
from odoo.tests.common import new_test_user


@tagged("voip")
class TestVoipAccessRights(common.TransactionCase):
    def _create_user_in_company(self, company, name, login, groups="base.group_user"):
        return new_test_user(
            self.env,
            login=login,
            groups=groups,
            company_id=company.id,
            name=name,
        )

    def test_officer_crud_access_to_company_calls(self):
        """
        Officers have full CRUD access to calls where call.user_id.company_id is their company.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        officer_user = self._create_user_in_company(company_a, "Officer", "officer", groups="voip.group_voip_officer")
        call_owner = self._create_user_in_company(company_a, "Taha Hussein", "tahaaaaaaaaaaaa")
        company_call = (
            self.env["voip.call"]
            .with_user(officer_user)
            .create({"user_id": call_owner.id, "phone_number": "123456789"})
        )

        self.assertTrue(company_call.with_user(officer_user).has_access("read"))
        self.assertTrue(company_call.with_user(officer_user).has_access("write"))
        self.assertTrue(company_call.with_user(officer_user).has_access("unlink"))
        self.assertTrue(company_call.with_user(officer_user).has_access("create"))

    def test_officer_restricted_access_to_other_company_calls(self):
        """
        Officers cannot perform CRUD on calls where user_id.company_id is not their company.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        company_b = self.env["res.company"].create({"name": "Company B"})
        officer_user = self._create_user_in_company(company_a, "Officer", "officer", groups="voip.group_voip_officer")
        other_company_user = self._create_user_in_company(company_b, "Tamer Elgyar", "fssssssssssss")
        other_company_call = self.env["voip.call"].create({"user_id": other_company_user.id, "phone_number": "987654321"})

        self.assertFalse(other_company_call.with_user(officer_user).has_access("read"))
        self.assertFalse(other_company_call.with_user(officer_user).has_access("write"))
        self.assertFalse(other_company_call.with_user(officer_user).has_access("unlink"))
        self.assertFalse(other_company_call.with_user(officer_user).has_access("create"))

    def test_admin_full_access_to_own_company_calls(self):
        """
        Admins have full CRUD access to calls where user_id.company_id is their company.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        admin_user = self._create_user_in_company(company_a, "Admin", "voip_admin", groups="voip.group_voip_admin")
        call_owner = self._create_user_in_company(company_a, "Jr Elaraby", "omar_gamal")
        company_call = (
            self.env["voip.call"]
            .with_user(admin_user)
            .create({"user_id": call_owner.id, "phone_number": "123456789"})
        )

        self.assertTrue(company_call.with_user(admin_user).has_access("create"))
        self.assertTrue(company_call.with_user(admin_user).has_access("read"))
        self.assertTrue(company_call.with_user(admin_user).has_access("write"))
        self.assertTrue(company_call.with_user(admin_user).has_access("unlink"))

    def test_admin_no_access_to_other_company_calls(self):
        """
        Admins do not have any access to calls where call.user_id.company_id is not their company.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        company_b = self.env["res.company"].create({"name": "Company B"})
        admin_user = self._create_user_in_company(company_a, "Admin", "voip_admin", groups="voip.group_voip_admin")
        other_company_user = self._create_user_in_company(company_b, "Nagiub Sawiris", "nagiub_mahfouz")
        other_company_call = self.env["voip.call"].create({"user_id": other_company_user.id, "phone_number": "987654321"})

        self.assertFalse(other_company_call.with_user(admin_user).has_access("create"))
        self.assertFalse(other_company_call.with_user(admin_user).has_access("read"))
        self.assertFalse(other_company_call.with_user(admin_user).has_access("write"))
        self.assertFalse(other_company_call.with_user(admin_user).has_access("unlink"))

    def test_regular_user_crud_on_their_own_calls(self):
        """
        Regular users can only perform read on their own call records.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        regular_user = self._create_user_in_company(company_a, "Regular", "regular")
        call_made_by_self = self.env["voip.call"].create({"user_id": regular_user.id, "phone_number": "987654321"})

        self.assertFalse(call_made_by_self.with_user(regular_user).has_access("create"))
        self.assertTrue(call_made_by_self.with_user(regular_user).has_access("read"))
        self.assertFalse(call_made_by_self.with_user(regular_user).has_access("write"))
        self.assertFalse(call_made_by_self.with_user(regular_user).has_access("unlink"))

    def test_regular_user_no_crud_on_others_calls(self):
        """
        Regular users cannot perform CRUD on other users' call records.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        regular_user = self._create_user_in_company(company_a, "Regular", "regular")
        other_user = self._create_user_in_company(company_a, "Wario", "waaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        call_made_by_other = self.env["voip.call"].create({"user_id": other_user.id, "phone_number": "+246 532 4846"})

        self.assertFalse(call_made_by_other.with_user(regular_user).has_access("create"))
        self.assertFalse(call_made_by_other.with_user(regular_user).has_access("read"))
        self.assertFalse(call_made_by_other.with_user(regular_user).has_access("write"))
        self.assertFalse(call_made_by_other.with_user(regular_user).has_access("unlink"))

    def test_regular_user_access_to_providers(self):
        """
        Regular users can only read provider records of their companies, not create, write, or unlink.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        company_b = self.env["res.company"].create({"name": "Company B"})
        regular_user = self._create_user_in_company(company_a, "Regular", "regular")
        provider_a = self.env["voip.provider"].create({"name": "Provider A", "company_id": company_a.id})
        provider_b = self.env["voip.provider"].create({"name": "Provider B", "company_id": company_b.id})

        self.assertFalse(provider_a.with_user(regular_user).has_access("create"))
        self.assertTrue(provider_a.with_user(regular_user).has_access("read"))
        self.assertFalse(provider_a.with_user(regular_user).has_access("write"))
        self.assertFalse(provider_a.with_user(regular_user).has_access("unlink"))
        self.assertFalse(provider_b.with_user(regular_user).has_access("create"))
        self.assertFalse(provider_b.with_user(regular_user).has_access("read"))
        self.assertFalse(provider_b.with_user(regular_user).has_access("write"))
        self.assertFalse(provider_b.with_user(regular_user).has_access("unlink"))

    def test_admin_access_to_providers(self):
        """
        Admins have full CRUD access to providers of their companies, but no access to other companies' providers.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        company_b = self.env["res.company"].create({"name": "Company B"})
        admin_user = self._create_user_in_company(company_a, "Admin", "voip_admin", groups="voip.group_voip_admin")
        provider_a = self.env["voip.provider"].create({"name": "Provider A", "company_id": company_a.id})
        provider_b = self.env["voip.provider"].create({"name": "Provider B", "company_id": company_b.id})

        self.assertTrue(provider_a.with_user(admin_user).has_access("create"))
        self.assertTrue(provider_a.with_user(admin_user).has_access("read"))
        self.assertTrue(provider_a.with_user(admin_user).has_access("write"))
        self.assertTrue(provider_a.with_user(admin_user).has_access("unlink"))
        self.assertFalse(provider_b.with_user(admin_user).has_access("create"))
        self.assertFalse(provider_b.with_user(admin_user).has_access("read"))
        self.assertFalse(provider_b.with_user(admin_user).has_access("write"))
        self.assertFalse(provider_b.with_user(admin_user).has_access("unlink"))
