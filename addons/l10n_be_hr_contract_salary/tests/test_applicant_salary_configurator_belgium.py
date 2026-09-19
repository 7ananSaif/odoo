from freezegun import freeze_time

from odoo.tests import tagged

from odoo.addons.hr_contract_salary.tests.test_applicant_salary_configurator import (
    TestSalaryConfiguratorForApplicant,
)


@tagged('-at_install', 'post_install', 'post_install_l10n', 'salary')
class TestSalaryConfiguratorForApplicantBelgium(TestSalaryConfiguratorForApplicant):
    @classmethod
    @freeze_time('2022-01-01 09:00:00')
    def setUpClass(cls):
        super().setUpClass()
        cls.senior_dev_contract.structure_type_id = cls.env.ref('hr.structure_type_employee_cp200').id

    def test_applicant_salary_configurator_flow(self):
        with freeze_time("2022-01-01 12:00:00"):
            self.start_tour("/", 'hr_contract_salary_applicant_flow_tour_belgium', login='admin', timeout=350)
            employee = self.env['hr.employee'].search([('name', 'ilike', 'Mitchell Admin 3'), ('active', '=', False)])
            self.assertEqual(employee.bank_account_ids.acc_holder_name, "Mohamed Dallash", "Account Holder name should have the same value as the one on the salary configurator")
