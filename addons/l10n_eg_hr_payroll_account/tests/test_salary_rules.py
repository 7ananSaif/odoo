# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    @classmethod
    @TestPayslipValidationCommon.setup_country('eg')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.eg'),
            structure=cls.env.ref('l10n_eg_hr_payroll.hr_payroll_structure_eg_employee_salary'),
            structure_type=cls.env.ref('l10n_eg_hr_payroll.structure_type_employee_eg'),
            contract_fields={
                'wage': 10000,
                'l10n_eg_housing_allowance': 100,
                'l10n_eg_transportation_allowance': 110,
                'l10n_eg_other_allowances': 80,
                'l10n_eg_social_insurance_reference': 1000,
                'l10n_eg_number_of_days': 5,
                'l10n_eg_total_number_of_days': 20,
            }
        )

    def test_basic_payslip(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SIEMP': -110.0, 'SICOMP': 187.5, 'ANNUALP': 600.25, 'GROSS': 10290.0, 'GROSSY': 122160.0, 'TAXBLEAM': 102160.0, 'TOTTB': -848.5, 'NET': 9331.5}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_service_payslip(self):
        annual_leave_type = self.env.ref('hr_holidays.leave_type_paid_time_off')
        self.employee.company_id.l10n_eg_annual_leave_type_id = annual_leave_type.id
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Annual Leave Allocation',
            'employee_id': self.employee.id,
            'date_from': date(2025, 1, 1),
            'holiday_status_id': annual_leave_type.id,
            'number_of_days': 15,
        })
        allocation.action_approve()
        self._generate_leave(date(2025, 1, 20), date(2025, 1, 21), annual_leave_type)
        self.employee.departure_date = date(2025, 1, 31)
        self.employee.departure_reason_id = self.env.ref('hr.departure_fired')
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SICOMP': 187.5, 'SIEMP': -110.0, 'EOSP': 142.92, 'ANNUALP': 600.25, 'ANNUALCOMP': 4459.0, 'EOSB': 6860.0, 'GROSS': 21609.0, 'GROSSY': 257988.0, 'TAXBLEAM': 237988.0, 'TOTTB': -3191.44, 'NET': 18307.56}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_with_other_input(self):
        self.employee.departure_date = date(2025, 1, 31)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        other_inputs_to_add = [
            (self.env.ref('l10n_eg_hr_payroll.l10n_eg_input_weekdays_overtime_daytime_hours'), 2),
            (self.env.ref('l10n_eg_hr_payroll.l10n_eg_input_weekend_public_holiday_overtime_hours'), 2),
        ]
        for other_input, amount in other_inputs_to_add:
            self._add_other_input(payslip, other_input, amount)
        payslip.compute_sheet()

        payslip_results = {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SICOMP': 187.5, 'SIEMP': -110.0, 'OVTWD': 112.03, 'OVTWEND': 165.97, 'EOSP': 142.92, 'ANNUALP': 600.25, 'EOSB': 6860.0, 'GROSS': 17428.0, 'GROSSY': 207815.95, 'TAXBLEAM': 187815.95, 'TOTTB': -2276.1, 'NET': 15041.9}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_with_unpaid_sick_leave(self):
        unpaid_sick_leave_type = self.env.ref('hr_holidays.l10n_eg_leave_type_sick_leave_unpaid')
        self._generate_leave(date(2025, 1, 16), date(2025, 1, 17), unpaid_sick_leave_type)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SIEMP': -110.0, 'SICOMP': 187.5, 'ANNUALP': 600.25, 'EGSICKLEAVE0': -686.0, 'GROSS': 10290.0, 'GROSSY': 113928.0, 'TAXBLEAM': 93928.0, 'TOTTB': -711.3, 'NET': 8782.7}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_with_75_paid_sick_leave(self):
        sick_leave_75_type = self.env.ref('hr_holidays.l10n_eg_leave_type_sick_leave_75')
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Sick Leave Allocation',
            'employee_id': self.employee.id,
            'date_from': date(2025, 1, 1),
            'holiday_status_id': sick_leave_75_type.id,
            'number_of_days': 2,
        })
        allocation.action_approve()
        self._generate_leave(date(2025, 1, 15), date(2025, 1, 16), sick_leave_75_type)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SIEMP': -110.0, 'SICOMP': 187.5, 'ANNUALP': 600.25, 'EGSICKLEAVE75': -171.5, 'GROSS': 10290.0, 'GROSSY': 120102.0, 'TAXBLEAM': 100102.0, 'TOTTB': -814.2, 'NET': 9194.3}
        self._validate_payslip(payslip, payslip_results)
