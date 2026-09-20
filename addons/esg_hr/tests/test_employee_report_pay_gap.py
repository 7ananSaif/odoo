from odoo.tests.common import TransactionCase

from odoo.addons.mail.tests.common import mail_new_test_user


class TestEmployeeReportPayGap(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_a = cls.env["res.company"].create({"name": "Test Company A"})
        cls.company_b = cls.env["res.company"].create({"name": "Test Company B"})
        cls.hr_user = mail_new_test_user(
            cls.env,
            login="hruser",
            groups="hr.group_hr_user",
            company_id=cls.company_a.id,
            company_ids=[cls.company_a.id, cls.company_b.id],
        )

    def create_emp(self, name, sex, company, wage):
        employee = self.env["hr.employee"].create({
            "name": name,
            "sex": sex,
            "company_id": company.id,
        })
        employee.current_version_id.wage = wage
        return employee

    def test_pay_gap_multi_company(self):
        report = self.env["esg.employee.report"].with_user(self.hr_user)

        self.create_emp("John A", "male", self.company_a, 3000)
        self.create_emp("John AA", "male", self.company_a, 6000)
        self.create_emp("John AAA", "male", self.company_a, 10000)  # Median = 6000

        self.create_emp("Jane A", "female", self.company_a, 2800)
        self.create_emp("Jane AA", "female", self.company_a, 4800)
        self.create_emp("Jane AAA", "female", self.company_a, 8800)  # Median = 4800

        self.create_emp("John B", "male", self.company_b, 5000)
        self.create_emp("Jane B", "female", self.company_b, 4000)

        gap_a = report.with_context(allowed_company_ids=[self.company_a.id]).get_overall_pay_gap()
        expected_a = round((6000 - 4800) / 6000 * 100, 2)
        self.assertEqual(gap_a, expected_a, "The pay gap should only take into account the employees from company A.")

        gap_b = report.with_context(allowed_company_ids=[self.company_b.id]).get_overall_pay_gap()
        expected_b = round((5000 - 4000) / 5000 * 100, 2)
        self.assertEqual(gap_b, expected_b, "The pay gap should only take into account the employees from company A.")

        gap_combined = report.with_context(
            allowed_company_ids=[self.company_a.id, self.company_b.id],
        ).get_overall_pay_gap()
        # Combined males: [3000, 5000, 6000, 10000] → median = (5000+6000)/2 = 5500
        # Combined females: [2800, 4000, 4800, 8800] → median = (4000+4800)/2 = 4400
        expected_combined = round((5500 - 4400) / 5500 * 100, 2)
        self.assertEqual(gap_combined, expected_combined, "The pay gap should take into account the employees from both companies.")

    def test_user_without_hr_rights(self):
        user = mail_new_test_user(
            self.env,
            login="norights",
            company_id=self.company_a.id,
        )
        gap = self.env["esg.employee.report"].with_user(user).with_context(
            allowed_company_ids=[self.company_a.id],
        ).get_overall_pay_gap()
        self.assertIsNone(gap, "A user with no HR access should get 'None' when calling the method.")

    def test_pay_gap_no_male_employees(self):
        self.create_emp("Jane A", "female", self.company_a, 4800)

        report = self.env["esg.employee.report"].with_user(self.hr_user)
        gap = report.with_context(allowed_company_ids=[self.company_a.id]).get_overall_pay_gap()
        self.assertFalse(gap, "No male salaries means a pay gap cannot be computed.")

    def test_pay_gap_no_female_employees(self):
        self.create_emp("John A", "male", self.company_a, 6000)

        report = self.env["esg.employee.report"].with_user(self.hr_user)
        gap = report.with_context(allowed_company_ids=[self.company_a.id]).get_overall_pay_gap()
        self.assertFalse(gap, "No female salaries means a pay gap cannot be computed.")

    def test_pay_gap_equal_wages(self):
        self.create_emp("John A", "male", self.company_a, 5000)
        self.create_emp("Jane A", "female", self.company_a, 5000)

        report = self.env["esg.employee.report"].with_user(self.hr_user)
        gap = report.with_context(allowed_company_ids=[self.company_a.id]).get_overall_pay_gap()
        self.assertEqual(gap, 0, "Equal wages should result in no pay gap")

    def test_negative_pay_gap(self):
        self.create_emp("Jane A1", "female", self.company_a, 6000)
        self.create_emp("Jane A2", "female", self.company_a, 5000)

        self.create_emp("John A1", "male", self.company_a, 3000)
        self.create_emp("John A2", "male", self.company_a, 4000)

        gap = self.env["esg.employee.report"].with_user(self.hr_user).with_context(
            allowed_company_ids=[self.company_a.id],
        ).get_overall_pay_gap()

        # Medians:
        #   Male: [3000, 4000] → 3500
        #   Female: [5000, 6000] → 5500
        expected = round((3500 - 5500) / 3500 * 100, 2)  # → -57.14%
        self.assertEqual(gap, expected, "The pay gap should be able to go negative.")
