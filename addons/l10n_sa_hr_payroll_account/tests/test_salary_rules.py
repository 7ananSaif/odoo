# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.fields import Command
from odoo.tests.common import tagged

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

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
                'wage': 10000.0,
                'l10n_sa_housing_allowance': 400.0,
                'l10n_sa_transportation_allowance': 200.0,
                'l10n_sa_other_allowances': 150.0,
                'l10n_sa_number_of_days': 20.0,
            }
        )
        cls.env.user.group_ids |= cls.env.ref('hr_holidays.group_hr_holidays_manager')

        cls.saudi_work_contact = cls.env['res.partner'].create({
            'name': 'KSA Local Employee',
            'company_id': cls.env.company.id,
        })

        cls.saudi_employee = cls.env['hr.employee'].create({
            'name': 'KSA Local Employee',
            'address_id': cls.saudi_work_contact.id,
            'company_id': cls.env.company.id,
            'country_id': cls.env.ref('base.sa').id,
            'structure_type_id': cls.env.ref('l10n_sa_hr_payroll.ksa_employee_payroll_structure_type').id,
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'wage': 12000,
            'l10n_sa_housing_allowance': 1000,
            'l10n_sa_transportation_allowance': 200,
            'l10n_sa_other_allowances': 500,
            'l10n_sa_number_of_days': 21,
            'l10n_sa_iqama_annual_amount': 6000.0,
            'l10n_sa_medical_insurance_annual_amount': 4800.0,
            'l10n_sa_work_permit_annual_amount': 3600.0,
        })
        cls.saudi_contract = cls.saudi_employee.version_id

        cls.compensable_timeoff_type = cls.env['hr.leave.type'].create({
            'name': "KSA Compensable Leaves",
            'company_id': cls.env.company.id,
        })

        cls.env.company.write({
            "l10n_sa_annual_leave_type_id": cls.compensable_timeoff_type.id,
        })

        cls.env['hr.leave.allocation'].create({
            'employee_id': cls.saudi_employee.id,
            'date_from': date(2024, 1, 1),
            'holiday_status_id': cls.compensable_timeoff_type.id,
            'number_of_days': 21,
            'state': 'confirm',
        }).action_approve()

    def test_saudi_payslip(self):
        payslip = self._generate_payslip(
            date(2024, 1, 1), date(2024, 1, 31),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {
            'BASIC': 12000.0,
            'GOSI_COMP': -1527.5,
            'GOSI_EMP': -1267.5,
            'HOUALLOW': 1000.0,
            'OTALLOW': 500.0,
            'TRAALLOW': 200.0,
            'EOSP': 570.83,
            'MEDICAL': 400.0,
            'IQAMA': 500.0,
            'WORKPER': 300.0,
            'ANNUALP': 799.17,
            'GROSS': 13700.0,
            'NET': 12432.5,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_saudi_payslip_laid_off(self):
        self.saudi_employee.write({
            'active': False,
            'departure_reason_id': self.env.ref('l10n_sa_hr_payroll.saudi_departure_clause_77').id,
            'departure_date': date(2024, 3, 31),
        })
        self.saudi_contract.date_end = date(2024, 3, 31)
        payslip = self._generate_payslip(
            date(2024, 3, 1), date(2024, 3, 31),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {
            'BASIC': 12000.0,
            'GOSI_COMP': -1527.5,
            'GOSI_EMP': -1267.5,
            'HOUALLOW': 1000.0,
            'OTALLOW': 500.0,
            'TRAALLOW': 200.0,
            'EOSALLOW': 27400.0,
            'EOSB': 13700.0,
            'ANNUALCOMP': 2397.5,
            'MEDICAL': 400.0,
            'IQAMA': 500.0,
            'WORKPER': 300.0,
            'GROSS': 54800.0,
            'NET': 53532.5,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_overtime_1(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        work_entry = self.env['hr.work.entry'].create({
            'name': 'OT',
            'employee_id': payslip.employee_id.id,
            'version_id': payslip.employee_id.version_id.id,
            'date': date(2024, 1, 1),
            'duration': 4,
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_overtime').id,
        })
        work_entry.action_validate()
        payslip.compute_sheet()
        payslip_results = {
            'BASIC': 10000.0,
            'GOSI_COMP': -1222.0,
            'GOSI_EMP': -1014.0,
            'HOUALLOW': 400.0,
            'OTALLOW': 150.0,
            'TRAALLOW': 200.0,
            'EOSP': 895.83,
            'ANNUALP': 597.22,
            'GROSS': 10750.0,
            'NET': 9736.0
        }
        self._validate_payslip(payslip, payslip_results)

    def test_salary_advance_payslip(self):
        # Should not use `_generate_payslip` because we need to make sure that `ADV` input line is created with 0.0 amount
        payslip = self.env['hr.payslip'].create([{
            'name': "Test Payslip",
            'employee_id': self.saudi_employee.id,
            'version_id': self.saudi_employee.version_id.id,
            'company_id': self.env.company.id,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan').id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
        }])

        self.assertEqual(payslip.input_line_ids.filtered(lambda x: x.code == 'ADV').amount, 0.0)
        payslip.input_line_ids.filtered(lambda x: x.code == 'ADV').amount = 2500.0

        payslip.compute_sheet()
        payslip_results = {'ADV': 2500.0, 'NET': 2500.0}
        self._validate_payslip(payslip, payslip_results)

    def test_saudi_payslip_after_salary_advance_payslip(self):
        adv_payslip = self.env['hr.payslip'].create([{
            'name': "Test Adv Payslip",
            'employee_id': self.saudi_employee.id,
            'version_id': self.saudi_employee.version_id.id,
            'company_id': self.env.company.id,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan').id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
        }])

        adv_payslip.input_line_ids.filtered(lambda x: x.code == 'ADV').amount = 2500.0
        adv_payslip.compute_sheet()
        adv_payslip.action_payslip_done()

        payslip = self.env['hr.payslip'].create([{
            'name': "Test Payslip",
            'employee_id': self.saudi_employee.id,
            'version_id': self.saudi_employee.version_id.id,
            'company_id': self.env.company.id,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id,
            'date_from': date(2024, 2, 1),
            'date_to': date(2024, 2, 29),
        }])

        self.assertEqual(payslip.input_line_ids.filtered(lambda x: x.code == 'ADV').amount, 2500.0)
        payslip.compute_sheet()

        self.assertEqual(payslip._get_line_values(['ADVDED'])['ADVDED'][payslip.id]['total'], -2500.0)

    def test_salary_loan_payslip(self):
        loan_attachment = self.env['hr.salary.attachment'].create({
            'employee_ids': [Command.link(self.saudi_employee.id)],
            'description': 'Car Loan',
            'other_input_type_id': self.env.ref('l10n_sa_hr_payroll.l10n_sa_input_loan_deduction').id,
            'date_start': date(2024, 1, 1),
            'monthly_amount': 200,
            'total_amount': 600,
        })

        loan_action = loan_attachment.action_create_loan_payslip()
        loan_payslip = self.env['hr.payslip'].browse(loan_action['res_id'])
        self.assertEqual(loan_payslip.input_line_ids.filtered(lambda x: x.code == 'LOAN_DEDUCTION').amount, 600.0)

        payslip = self.env['hr.payslip'].create([{
            'name': "Test Payslip",
            'employee_id': self.saudi_employee.id,
            'version_id': self.saudi_employee.version_id.id,
            'company_id': self.env.company.id,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
        }])

        self.assertEqual(payslip.input_line_ids.filtered(lambda x: x.code == 'LOAN_DEDUCTION').amount, 200.0)
        payslip.compute_sheet()

        self.assertEqual(payslip._get_line_values(['LOAN_DEDUCTION'])['LOAN_DEDUCTION'][payslip.id]['total'], -200.0)
