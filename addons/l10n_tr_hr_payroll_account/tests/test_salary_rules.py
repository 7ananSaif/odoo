# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.fields import Command
from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    @classmethod
    @TestPayslipValidationCommon.setup_country('tr')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.tr'),
            structure=cls.env.ref('l10n_tr_hr_payroll.hr_payroll_structure_tr_employee_salary'),
            structure_type=cls.env.ref('l10n_tr_hr_payroll.structure_type_employee_tr'),
            contract_fields={
                'wage': 50000,
                'l10n_tr_is_net_to_gross': False,
            }
        )

    def test_basic_payslip(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {
            "YTDGROSS": 0.0,
            "BASIC": 50000.0,
            "SSIEDED": -7000.0,
            "SSIDED": -500.0,
            "SSICDED": 7750.0,
            "SSIUCDED": 1000.0,
            "GROSS": 42500.0,
            "CURTAXABLE": 42500.0,
            "TAXB": 42500.0,
            "TOTTB": 6375.0,
            "ACTD": 0.0,
            "BTAXNET": 6375.0,
            "BTNET": -3824.68,
            "STAX": -227.68,
            "NETTAX": -4052.36,
            "EXPNET": 38447.64,
            "NET": 38447.64,
        }
        self._validate_payslip(payslip, payslip_results)
        payslip.action_payslip_done()
        payslip.action_payslip_paid()

        payslip_second_month = self._generate_payslip(date(2024, 2, 1), date(2024, 2, 29))
        payslip_second_month_results = {
            "YTDGROSS": 42500.0,
            "BASIC": 50000.0,
            "SSIEDED": -7000.0,
            "SSIDED": -500.0,
            "SSICDED": 7750.0,
            "SSIUCDED": 1000.0,
            "GROSS": 85000.0,
            "CURTAXABLE": 42500.0,
            "TAXB": 85000.0,
            "TOTTB": 12750.0,
            "ACTD": 6375.0,
            "BTAXNET": 6375.0,
            "BTNET": -3824.68,
            "STAX": -227.68,
            "NETTAX": -4052.36,
            "EXPNET": 38447.64,
            "NET": 38447.64,
        }
        self._validate_payslip(payslip_second_month, payslip_second_month_results)
        payslip_second_month.action_payslip_done()
        payslip_second_month.action_payslip_paid()

        payslip_third_month = self._generate_payslip(date(2024, 3, 1), date(2024, 3, 31))
        payslip_third_month_results = {
            "YTDGROSS": 850000.0,
            "BASIC": 50000.0,
            "SSIEDED": -7000.0,
            "SSIDED": -500.0,
            "SSICDED": 7750.0,
            "SSIUCDED": 1000.0,
            "GROSS": 127500.0,
            "CURTAXABLE": 42500.0,
            "TAXB": 127500.0,
            "TOTTB": 20000.0,
            "ACTD": 12750.0,
            "BTAXNET": 7250.0,
            "BTNET": -4699.68,
            "STAX": -227.68,
            "NETTAX": -4927.36,
            "EXPNET": 37572.64,
            "NET": 37572.64,
        }

        payslip_second_month.action_payslip_cancel()
        payslip_third_month.compute_sheet()
        payslip_third_month_results = payslip_second_month_results
        self._validate_payslip(payslip_third_month, payslip_third_month_results)

    def test_ntg_payslip(self):
        self.contract.l10n_tr_is_net_to_gross = True
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {
            "YTDGROSS": 0.0,
            "ACTD": 0.00,
            "GFNET": 65024.86,
            "BASIC": 65024.86,
            "SSIEDED": -9103.48,
            "SSIDED": -650.25,
            "SSICDED": 10078.85,
            "SSIUCDED": 1300.50,
            "GROSS": 55271.13,
            "CURTAXABLE": 55271.13,
            "TAXB": 55271.13,
            "TOTTB": 8290.67,
            "BTAXNET": 8290.67,
            "BTNET": -4974.97,
            "STAX": -296.16,
            "NETTAX": -5271.13,
            "EXPNET": 50000.00,
            "NET": 50000.00,
        }
        self._validate_payslip(payslip, payslip_results)
        payslip.action_payslip_done()
        payslip.action_payslip_paid()

        payslip_second_month = self._generate_payslip(date(2025, 2, 1), date(2025, 2, 28))
        payslip_second_month_results = {
            "YTDGROSS": 55271.13,
            "ACTD": 8290.67,
            "GFNET": 65024.86,
            "BASIC": 65024.86,
            "SSIEDED": -9103.48,
            "SSIDED": -650.25,
            "SSICDED": 10078.85,
            "SSIUCDED": 1300.50,
            "GROSS": 110542.26,
            "CURTAXABLE": 55271.13,
            "TAXB": 110542.26,
            "TOTTB": 16581.34,
            "BTAXNET": 8290.67,
            "BTNET": -4974.97,
            "STAX": -296.16,
            "NETTAX": -5271.13,
            "EXPNET": 50000.00,
            "NET": 50000.00,
        }
        self._validate_payslip(payslip_second_month, payslip_second_month_results)
        payslip_second_month.action_payslip_done()
        payslip_second_month.action_payslip_paid()

        payslip_third_month = self._generate_payslip(date(2025, 3, 1), date(2025, 3, 31))
        payslip_third_month_results = {
            "YTDGROSS": 110542.26,
            "ACTD": 16581.34,
            "GFNET": 65605.85,
            "BASIC": 65605.85,
            "SSIEDED": -9184.82,
            "SSIDED": -656.06,
            "SSICDED": 10168.91,
            "SSIUCDED": 1312.12,
            "GROSS": 166307.23,
            "CURTAXABLE": 55764.97,
            "TAXB": 166307.23,
            "TOTTB": 25361.44,
            "BTAXNET": 8780.10,
            "BTNET": -5464.40,
            "STAX": -300.57,
            "NETTAX": -5764.97,
            "EXPNET": 50000.00,
            "NET": 50000.00,
        }

        payslip_second_month.action_payslip_cancel()
        payslip_third_month.compute_sheet()
        payslip_third_month_results = payslip_second_month_results
        self._validate_payslip(payslip_third_month, payslip_third_month_results)

    def test_ntg_payslip_deduction(self):
        self.contract.l10n_tr_is_net_to_gross = True
        input_lines = [
            Command.create({
                'name': 'Manual Deduction',
                'input_type_id': self.env.ref('l10n_tr_hr_payroll.input_manual_deduction').id,
                'amount': 100,
            }),
            Command.create({
                'name': 'Manual Additions',
                'input_type_id': self.env.ref('l10n_tr_hr_payroll.input_manual_addition').id,
                'amount': 200,
            }),
            Command.create({
                'name': 'Manual Additions 2',
                'input_type_id': self.env.ref('l10n_tr_hr_payroll.input_manual_addition').id,
                'amount': 95,
            }),
        ]
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31), input_line_ids=input_lines)
        payslip_results = {
            "YTDGROSS": 0.0,
            "ACTD": 0.00,
            "GFNET": 65024.86,
            "BASIC": 65024.86,
            "SSIEDED": -9103.48,
            "SSIDED": -650.25,
            "SSICDED": 10078.85,
            "SSIUCDED": 1300.50,
            "GROSS": 55271.13,
            "CURTAXABLE": 55271.13,
            "TAXB": 55271.13,
            "TOTTB": 8290.67,
            "BTAXNET": 8290.67,
            "BTNET": -4974.97,
            "STAX": -296.16,
            "NETTAX": -5271.13,
            "EXPNET": 50000.00,
            "MANADD": 295.00,
            "MANDED": 100.00,
            "NET": 50195.00,
        }
        self._validate_payslip(payslip, payslip_results)
