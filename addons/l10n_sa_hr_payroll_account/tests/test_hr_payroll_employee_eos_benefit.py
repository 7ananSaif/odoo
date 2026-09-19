# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestHrPayrollEmployeeEosBenefit(TestPayslipValidationCommon):

    @classmethod
    @TestPayslipValidationCommon.setup_country('sa')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls._setup_common(
            country=cls.env.ref('base.sa'),
            structure=cls.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure'),
            structure_type=cls.env.ref('l10n_sa_hr_payroll.ksa_employee_payroll_structure_type'),
            contract_fields={
                'wage': 10000,
            }
        )

    def test_sa_end_of_service_benefit(self):
        self.employee.version_id.contract_date_start = date(2023, 4, 18)
        self.employee.version_id.contract_date_end = date(2025, 6, 9)
        self.employee.write({
            'active': False,
            'departure_reason_id': self.env.ref('l10n_sa_hr_payroll.saudi_departure_end_of_contract').id,
            'departure_date': date(2025, 6, 9),
        })
        payslip = self._generate_payslip(date(2025, 7, 1), date(2025, 7, 31))

        # test end of contract with actual of number of days
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 10736.11, 2)

        self.employee.version_id.contract_date_start = date(2020, 3, 31)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 26944.44, 2)

        self.employee.version_id.contract_date_start = date(2014, 6, 30)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 84472.22, 2)

        # test resignation with actual of number of days
        self.employee.departure_reason_id = self.env.ref('hr.departure_resigned').id

        self.employee.version_id.contract_date_start = date(2023, 4, 18)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 3578.70, 2)

        self.employee.version_id.contract_date_start = date(2020, 3, 31)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 8657.41, 2)

        self.employee.version_id.contract_date_start = date(2014, 6, 30)
        payslip.compute_sheet()
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'EOSB').total, 84472.22, 2)
