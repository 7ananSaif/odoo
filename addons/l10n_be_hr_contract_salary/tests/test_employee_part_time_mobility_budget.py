import odoo.tests
from odoo.addons.hr_contract_salary.tests.test_salary_package import TestSalaryPackageItems


@odoo.tests.tagged('post_install_l10n', '-at_install', 'post_install', 'salary')
class TestEmployeePartTimeMB(TestSalaryPackageItems):

    def test_employee_part_time_with_mobility_budget(self):
        active_version = self.env['hr.version'].search([('employee_id', '=', self.employee.id), ('active', '=', True)])[0]
        active_version.wage = 5000
        active_version.holidays = 10
        active_version.work_time_rate = 0.5
        self.assertEqual(active_version.wage_with_holidays, 4769.12)
        self.assertEqual(active_version.l10n_be_wage_with_mobility_budget, 4769.12)
        # Activate mobility budget and check full time equivalent amounts
        active_version.l10n_be_mobility_budget = True
        self.assertEqual(active_version.l10n_be_mobility_budget_amount, 12399.71)
        self.assertEqual(active_version.l10n_be_wage_with_mobility_budget, 4058.46)
        # Make part time simulation
        active_version._generate_salary_simulation_payslip()
        self.assertEqual(active_version.wage_with_holidays, 2377.35)
        self.assertEqual(active_version.l10n_be_wage_with_mobility_budget, 1666.69)
        # Should not change the mobility budget
        self.assertEqual(active_version.l10n_be_mobility_budget_amount, 12399.71)
