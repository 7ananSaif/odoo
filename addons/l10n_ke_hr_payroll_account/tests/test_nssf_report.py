# Part of Odoo. See LICENSE file for full copyright and licensing details.

import freezegun
from datetime import date

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestNSSFReport(TestPayslipValidationCommon):

    @classmethod
    @TestPayslipValidationCommon.setup_country('ke')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.ke'),
            structure=cls.env.ref('l10n_ke_hr_payroll.hr_payroll_structure_ken_employee_salary'),
            structure_type=cls.env.ref('l10n_ke_hr_payroll.structure_type_employee_ken'),
            contract_fields={
                'date_version': '2025-01-01',
                'contract_date_start': '2025-01-01',
                'wage': 100000.0,
                'l10n_ke_tier_2_remit': 'insurance',
                'l10n_ke_pension_remit': 'insurance',
            }
        )

    def create_nssf_report(self):
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        return self.env['l10n.ke.hr.payroll.nssf.report.wizard'].with_company(self.company).create({
            'company_id': self.company.id,
            'reference_year': '2025',
            'reference_month': '1',
        })

    @freezegun.freeze_time('2025-01-01')
    def test_nssf_tiers_1(self):
        nssf_report = self.create_nssf_report()
        self.assertEqual(len(nssf_report.line_ids), 1)
        self.assertEqual(nssf_report.line_ids[0].payslip_nssf_code, '101')
        self.assertAlmostEqual(nssf_report.line_ids[0].payslip_nssf_amount_employee, 420, 2)

    @freezegun.freeze_time('2025-01-01')
    def test_nssf_tiers_1_2(self):
        self.employee.l10n_ke_tier_2_remit = 'nssf'

        nssf_report = self.create_nssf_report()
        self.assertEqual(len(nssf_report.line_ids), 2)
        self.assertEqual(nssf_report.line_ids[0].payslip_nssf_code, '101')
        self.assertAlmostEqual(nssf_report.line_ids[0].payslip_nssf_amount_employee, 420, 2)
        self.assertEqual(nssf_report.line_ids[1].payslip_nssf_code, '102')
        self.assertAlmostEqual(nssf_report.line_ids[1].payslip_nssf_amount_employee, 1740, 2)

    @freezegun.freeze_time('2025-01-01')
    def test_nssf_tiers_1_3(self):
        self.employee.l10n_ke_pension_remit = 'nssf'
        self.employee.l10n_ke_pension_contribution = 500

        nssf_report = self.create_nssf_report()
        self.assertEqual(len(nssf_report.line_ids), 2)
        self.assertEqual(nssf_report.line_ids[0].payslip_nssf_code, '101')
        self.assertAlmostEqual(nssf_report.line_ids[0].payslip_nssf_amount_employee, 420, 2)
        self.assertEqual(nssf_report.line_ids[1].payslip_nssf_code, '103')
        self.assertAlmostEqual(nssf_report.line_ids[1].payslip_nssf_amount_employee, 500, 2)

    @freezegun.freeze_time('2025-01-01')
    def test_nssf_tiers_1_2_3(self):
        self.employee.l10n_ke_tier_2_remit = 'nssf'
        self.employee.l10n_ke_pension_remit = 'nssf'
        self.employee.l10n_ke_pension_contribution = 500

        nssf_report = self.create_nssf_report()
        self.assertEqual(len(nssf_report.line_ids), 3)
        self.assertEqual(nssf_report.line_ids[0].payslip_nssf_code, '101')
        self.assertAlmostEqual(nssf_report.line_ids[0].payslip_nssf_amount_employee, 420, 2)
        self.assertEqual(nssf_report.line_ids[1].payslip_nssf_code, '102')
        self.assertAlmostEqual(nssf_report.line_ids[1].payslip_nssf_amount_employee, 1740, 2)
        self.assertEqual(nssf_report.line_ids[2].payslip_nssf_code, '103')
        self.assertAlmostEqual(nssf_report.line_ids[2].payslip_nssf_amount_employee, 500, 2)

    @freezegun.freeze_time('2025-01-01')
    def test_nssf_tiers_1_2_3_no_pension_contribution(self):
        self.employee.l10n_ke_tier_2_remit = 'nssf'
        self.employee.l10n_ke_pension_remit = 'nssf'

        # When there is no pension contribution, there is no tier 3 in the report
        nssf_report = self.create_nssf_report()
        self.assertEqual(len(nssf_report.line_ids), 2)
        self.assertEqual(nssf_report.line_ids[0].payslip_nssf_code, '101')
        self.assertAlmostEqual(nssf_report.line_ids[0].payslip_nssf_amount_employee, 420, 2)
        self.assertEqual(nssf_report.line_ids[1].payslip_nssf_code, '102')
        self.assertAlmostEqual(nssf_report.line_ids[1].payslip_nssf_amount_employee, 1740, 2)
