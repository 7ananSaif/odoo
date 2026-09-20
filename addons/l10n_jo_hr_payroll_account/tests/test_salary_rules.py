# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    @classmethod
    @TestPayslipValidationCommon.setup_country('jo')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.jo'),
            structure=cls.env.ref('l10n_jo_hr_payroll.hr_payroll_structure_jo_employee_salary'),
            structure_type=cls.env.ref('l10n_jo_hr_payroll.structure_type_employee_jo'),
            contract_fields={
                'wage': 40000.0,
                'l10n_jo_housing_allowance': 400.0,
                'l10n_jo_transportation_allowance': 220.0,
                'l10n_jo_other_allowances': 100.0,
            }
        )

    def test_payslip_1(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {
            'BASIC': 40000.0,
            'HOUALLOW': 400.0,
            'TRAALLOW': 220.0,
            'OTALLOW': 100.0,
            'SSC': -477.233,
            'SSE': -251.175,
            'EOSPROV': 3393.333,
            'ANNUALP': 1583.556,
            'GROSS': 40720.0,
            'GROSSY': 476640.0,
            'TXB': -9721.666,
            'NET': 30747.159
        }
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_sick_leave_unpaid(self):
        unpaid_sick_leave_type = self.env.ref('hr_holidays.l10n_jo_leave_type_unpaid_sick')
        self._generate_leave(date(2025, 1, 9), date(2025, 1, 10), unpaid_sick_leave_type)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 40000.0,
            'HOUALLOW': 400.0,
            'TRAALLOW': 220.0,
            'OTALLOW': 100.0,
            'SSC': -477.233,
            'SSE': -251.175,
            'SICKLEAVE0': -2714.667,
            'EOSPROV': 3393.333,
            'ANNUALP': 1583.556,
            'GROSS': 40720.0,
            'GROSSY': 476640.0,
            'TXB': -9721.666,
            'NET': 28032.492
        }
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_end_of_service(self):
        annual_leave_type = self.env.ref('hr_holidays.leave_type_paid_time_off')
        self.employee.company_id.l10n_jo_annual_leave_type_id = annual_leave_type.id
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Annual Leave Allocation',
            'employee_id': self.employee.id,
            'date_from': date(2025, 1, 1),
            'holiday_status_id': annual_leave_type.id,
            'number_of_days': 14,
        })
        allocation.action_approve()
        self._generate_leave(date(2025, 1, 10), date(2025, 1, 13), annual_leave_type)
        self.employee.l10n_jo_is_eligible_for_eos = True
        self.employee.version_id.contract_date_end = date(2025, 3, 31)
        self.employee.departure_date = date(2025, 3, 31)
        self.employee.departure_reason_id = self.env.ref('hr.departure_fired')
        payslip = self._generate_payslip(date(2025, 3, 1), date(2025, 3, 31))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 40000.0,
            'HOUALLOW': 400.0,
            'TRAALLOW': 220.0,
            'OTALLOW': 100.0,
            'SSC': -477.233,
            'SSE': -251.175,
            'EOSPROV': 3393.333,
            'ANNUALP': 1583.556,
            'GROSS': 40720.0,
            'GROSSY': 476640.0,
            'TXB': -9721.666,
            'EOSB': 376613.516,
            'EOSLEAVES': 4750.667,
            'EOSTXD': -90403.372,
            'NET': 321707.97,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_overtime_calculations(self):
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        other_inputs_to_add = [
            (self.env.ref('l10n_jo_hr_payroll.l10n_jo_input_restdays_overtime_hours'), 1),
            (self.env.ref('l10n_jo_hr_payroll.l10n_jo_input_weekdays_overtime_hours'), 2),
        ]
        for other_input, amount in other_inputs_to_add:
            self._add_other_input(payslip, other_input, amount)
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 40000.0,
            'HOUALLOW': 400.0,
            'TRAALLOW': 220.0,
            'OTALLOW': 100.0,
            'SSC': -477.233,
            'SSE': -251.175,
            'ROVT': 246.290,
            'WOVT': 410.484,
            'EOSPROV': 3393.333,
            'ANNUALP': 1583.556,
            'GROSS': 41376.774,
            'GROSSY': 484521.29,
            'TXB': -9885.86,
            'NET': 31239.74,
        }
        self._validate_payslip(payslip, payslip_results)
