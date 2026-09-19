# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
import datetime

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    @classmethod
    @TestPayslipValidationCommon.setup_country('in')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.in'),
            structure=cls.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_employee_salary'),
            structure_type=cls.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_emp'),
        )

    def test_regular_payslip_1(self):
        self.contract.write({
            'wage': 32000,
            'l10n_in_provident_fund': True,
            'l10n_in_esic': True,
            'l10n_in_pt': True,
            'l10n_in_basic_percentage': 0.5,
            'l10n_in_hra_percentage': 0.5,
            'l10n_in_standard_allowance': 4167,
            'l10n_in_esic_employee_percentage': 0.01,
            'l10n_in_esic_employer_percentage': 0.04,
            'l10n_in_performance_bonus_percentage': 0.0833,
            'l10n_in_leave_travel_percentage': 0.0833,
            'l10n_in_medical_insurance': 980.0,
            'l10n_in_insured_spouse': True,
            'l10n_in_insured_first_children': True,
            'l10n_in_phone_subscription': 500.0,
            'l10n_in_internet_subscription': 300.0,
            'l10n_in_meal_voucher_amount': 1000.0,
            'l10n_in_company_transport': 200.0,
            'pt_rule_parameter_id': self.env.ref('l10n_in_hr_payroll.l10n_in_rule_parameter_pt_gujarat').id,
        })

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 16000.0, 'HRA': 8000.0, 'STD': 4167.0, 'P_BONUS': 1332.8, 'LTA': 1332.8, 'SPL': 1167.4, 'MOB': 500.0, 'INT': 300.0, 'MEAL': 1000.0, 'CAR': 200.0, 'GROSS': 34000.0, 'PT': -200.0, 'PF': -1800.0, 'PFE': -1800.0, 'MED': -2940.0, 'NET': 27260.0}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_esic_threshold(self):
        self.contract.write({
            'wage': 20000,
            'l10n_in_basic_percentage': 1.0,
            'l10n_in_hra_percentage': 0.0,
            'l10n_in_standard_allowance': 0.0,
            'l10n_in_performance_bonus_percentage': 0.0,
            'l10n_in_leave_travel_percentage': 0.0,
            'l10n_in_fixed_allowance_percentage': 0.0,
            'l10n_in_phone_subscription': 0.0,
            'l10n_in_internet_subscription': 0.0,
            'l10n_in_meal_voucher_amount': 0.0,
            'l10n_in_company_transport': 0.0,
            'l10n_in_medical_insurance': 0.0,
            'l10n_in_insured_spouse': False,
            'l10n_in_insured_first_children': False,
            'l10n_in_esic': True,
            'l10n_in_esic_employee_percentage': 0.01,
            'l10n_in_esic_employer_percentage': 0.04,
        })

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 20000.0, 'GROSS': 20000.0, 'ESICS': -200.0, 'ESICF': -800.0, 'NET': 19000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_2(self):
        self.contract.company_id.write({
            'l10n_in_provident_fund': True,
            'l10n_in_pt': True,
        })
        self.contract.write({
            'wage': 16000,
            'l10n_in_basic_percentage': 0.35,
            'l10n_in_hra_percentage': 0.4,
            'l10n_in_standard_allowance': 4167,
            'l10n_in_performance_bonus_percentage': 0.3,
            'l10n_in_leave_travel_percentage': 0.3,
            'l10n_in_medical_insurance': 560.0,
            'l10n_in_insured_spouse': True,
            'l10n_in_gratuity_percentage': 0.0481,
            'sex': 'male',
            'pt_rule_parameter_id': self.env.ref('l10n_in_hr_payroll.l10n_in_rule_parameter_pt_maharashtra').id,
        })
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 5600.0, 'HRA': 2240.0, 'STD': 4167.0, 'P_BONUS': 1680.0, 'LTA': 1680.0, 'SPL': 633.0, 'GROSS': 16000.0, 'PT': -200.0, 'PF': -672.0, 'PFE': -672.0, 'GRATUITY': -269.36, 'MED': -1120.0, 'NET': 13066.64}
        self._validate_payslip(payslip, payslip_results)
        self.contract.sex = 'female'
        payslip.compute_sheet()
        payslip_results['PT'] = 0.0
        payslip_results['NET'] = 13266.64
        self._validate_payslip(payslip, payslip_results)

    def test_stipend_payslip_1(self):
        structure = self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_stipend')
        structure_type = self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_emp')
        self.contract.write({
            'wage': 10000,
            'structure_type_id': structure_type.id,
        })
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31), struct_id=structure.id)
        payslip_results = {'GROSS': 10000.0, 'NET': 10000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_stipend_payslip_2(self):
        structure = self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_stipend')
        structure_type = self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_emp')
        self.contract.write({
            'wage': 20000,
            'structure_type_id': structure_type.id,
        })
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31), struct_id=structure.id)
        payslip_results = {'GROSS': 20000.0, 'NET': 20000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_with_public_holiday(self):
        self.contract.write({
            'wage': 32000,
            'l10n_in_provident_fund': True,
            'l10n_in_esic': True,
            'l10n_in_pt': True,
            'l10n_in_basic_percentage': 0.5,
            'l10n_in_hra_percentage': 0.5,
            'l10n_in_standard_allowance': 4167,
            'l10n_in_esic_employee_percentage': 0.01,
            'l10n_in_esic_employer_percentage': 0.04,
            'l10n_in_performance_bonus_percentage': 0.0833,
            'l10n_in_leave_travel_percentage': 0.0833,
            'l10n_in_medical_insurance': 980.0,
            'l10n_in_insured_spouse': True,
            'l10n_in_insured_first_children': True,
            'l10n_in_phone_subscription': 500.0,
            'l10n_in_internet_subscription': 300.0,
            'l10n_in_meal_voucher_amount': 1000.0,
            'l10n_in_company_transport': 200.0,
            'pt_rule_parameter_id': self.env.ref('l10n_in_hr_payroll.l10n_in_rule_parameter_pt_gujarat').id,
        })
        self.env['resource.calendar.leaves'].create([{
            'name': "Absence",
            'company_id': self.env.company.id,
            'resource_id': self.employee.resource_id.id,
            'date_from': datetime.datetime(2024, 1, 8, 6, 0, 0),
            'date_to': datetime.datetime(2024, 1, 9, 19, 0, 0),
            'time_type': "leave",
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_unpaid_leave').id
        }])

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        self.assertEqual(len(payslip.worked_days_line_ids), 2)
        self.assertEqual(len(payslip.input_line_ids), 0)
        self.assertEqual(len(payslip.line_ids), 16)
        self._validate_worked_days(payslip, {
            'LEAVE90': (1.0, 11.0, 0.0),
            'WORK100': (22.0, 173.0, 30086.96),
        })
        payslip_results = {'BASIC': 15043.48, 'HRA': 7521.74, 'STD': 3917.89, 'P_BONUS': 1253.12, 'LTA': 1253.12, 'SPL': 1097.61, 'MOB': 500.0, 'INT': 300.0, 'MEAL': 1000.0, 'CAR': 200.0, 'GROSS': 32086.96, 'PT': -200.0, 'PF': -1692.39, 'PFE': -1692.39, 'MED': -2940.0, 'NET': 25562.18}
        self._validate_payslip(payslip, payslip_results)
