from datetime import date

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_eco_vouchers')
class TestPayrollEcoVouchers(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.george_payslip = cls.env["hr.payslip"].create({
            "struct_id": cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            "name": "Test Eco-Vouchers",
            "employee_id": cls.employee_georges.id,
            "version_id": cls.employee_georges.version_id.id,
            "date_from": date(2024, 9, 1),
            "date_to": date(2024, 9, 30),
            "company_id": cls.belgian_company.id
        })

        cls.john_payslip = cls.env["hr.payslip"].create({
            "struct_id": cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            "name": "Test Eco-Vouchers Edited Payslip",
            "employee_id": cls.employee_john.id,
            "version_id": cls.employee_john.version_id.id,
            "date_from": date(2024, 9, 1),
            "date_to": date(2024, 9, 30),
            "company_id": cls.belgian_company.id,
            "edited": True,
        })

        cls.eco_voucher_batch = cls.env["hr.payslip.run"].create({
            "name": "Eco-Vouchers",
            "slip_ids": [cls.george_payslip.id, cls.john_payslip.id],
            "date_start": date(2024, 9, 1),
            "date_end": date(2024, 10, 1),
            "company_id": cls.belgian_company.id
        })

        cls.eco_voucher_wizard = cls.env["l10n.be.eco.vouchers.wizard"].create({
            'company_id': cls.belgian_company.id,
            'line_ids': cls.env["l10n.be.eco.vouchers.line.wizard"].create([
                {
                    "employee_id": cls.employee_georges.id,  # It will use an existing payslip
                },
                {
                    "employee_id": cls.employee_test.id,  # It will generate a payslip
                },
                {
                    "employee_id": cls.employee_john.id,   # It will use an edited existing payslip
                },
            ]).ids,
        }).with_context({
            'batch_id': cls.eco_voucher_batch.id,
        })

    def test_eco_vouchers(self):
        self.eco_voucher_wizard.generate_payslips()

        self.assertEqual(
            any(input_line.code == 'ECOVOUCHERS' for input_line in self.george_payslip.line_ids),
            True,
            'Eco-vouchers line should be added on the payslip.'

        )
        self.assertEqual(
            any(input_line.code == 'ECOVOUCHERS' for input_line in self.john_payslip.line_ids),
            True,
            'Eco-vouchers line should be added on the edited payslip.'
        )

        self.test_payslip = self.eco_voucher_batch.slip_ids.filtered(lambda payslip: payslip.employee_id == self.employee_test)

        self.assertEqual(
            any(input_line.code == 'ECOVOUCHERS' for input_line in self.test_payslip.line_ids),
            True,
            'Eco-vouchers line should be added on the generated payslip.'
        )
