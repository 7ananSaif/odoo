# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestHrPayrollPayrollAcerta(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.belgium = cls.env.ref('base.be')
        cls.company = cls.env['res.company'].create({
            'name': 'Test Belgium Company',
            'country_id': cls.belgium.id,
            'acerta_code': '1234567',
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'company_id': cls.company.id,
        })

        cls.version = cls.env['hr.version'].create({
            'name': 'Test Version',
            'employee_id': cls.employee.id,
            'company_id': cls.company.id,
            'contract_date_start': datetime(2024, 10, 1),
            'contract_date_end': datetime(2024, 10, 31),
            'acerta_code': '12345678901234567890',
            'wage': 3000,
            'date_version': datetime(2024, 10, 1).date(),
        })

        cls.work_entry_type = cls.env['hr.work.entry.type'].create({
            'name': 'Test Work Entry Type',
            'code': 'WORKTEST',
            'acerta_code': '1234',
        })

    def test_hr_version_acerta_code_zfill(self):
        """Test hr.version acerta_code shorter than 20 chars is zero-padded"""
        self.version.write({'acerta_code': '12345'})
        self.assertEqual(len(self.version.acerta_code), 20)
        self.assertTrue(self.version.acerta_code.endswith('12345'))

    def test_work_entry_type_acerta_code_validation(self):
        """Test hr.work.entry.type acerta_code validation (must be 3-6 characters)"""
        with self.assertRaises(ValidationError):
            self.work_entry_type.write({'acerta_code': '12'})
        with self.assertRaises(ValidationError):
            self.work_entry_type.write({'acerta_code': '1234567'})
        self.work_entry_type.write({'acerta_code': '4321'})
        self.assertEqual(
            self.work_entry_type.acerta_code,
            '4321',
            "Acerta code should be valid when between 3 and 6 characters long"
        )

    def test_company_acerta_code_validation(self):
        """Test res.company acerta_code validation (must be exactly 7 characters)"""
        with self.assertRaises(ValidationError):
            self.company.write({'acerta_code': '1234'})
        with self.assertRaises(ValidationError):
            self.company.write({'acerta_code': '12345678'})

        self.company.write({'acerta_code': '7654321'})
        self.assertEqual(
            self.company.acerta_code,
            '7654321',
            "Acerta code should be valid when exactly 7 characters long"
        )

    def test_full_acerta_export_flow(self):
        """Test creating an Acerta export, populating, and generating the export file without errors"""
        work_entry = self.env['hr.work.entry'].create({
            'name': 'Work Entry',
            'company_id': self.company.id,
            'employee_id': self.employee.id,
            'work_entry_type_id': self.work_entry_type.id,
            'date': self.version.contract_date_start,
            'version_id': self.version.id,
        })
        work_entry.action_validate()

        export = self.env['l10n.be.hr.payroll.export.acerta'].with_company(self.company.id).create({
            'company_id': self.company.id,
            'reference_month': '10',
            'reference_year': 2024,
        })
        export.action_populate()

        self.assertTrue(export.eligible_employee_line_ids)
        self.assertIn(self.employee, export.eligible_employee_line_ids.employee_id)

        export.action_export_file()
        self.assertTrue(export.export_file)
