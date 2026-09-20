# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import RedirectWarning, ValidationError


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestHrContractGroupSCode(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.belgium = cls.env.ref('base.be')
        cls.company = cls.env['res.company'].create({
            'name': 'Test Belgium Company',
            'country_id': cls.belgium.id,
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'company_id': cls.company.id,
            'wage': 3000,
            'group_s_code': '123456',
            'country_code': 'BE',
        })

        cls.work_entry_type = cls.env['hr.work.entry.type'].create({
            'name': 'Test Work Entry Type',
            'code': 'WORKTEST',
            'group_s_code': '321',
        })

        cls.contract = cls.employee.version_id

    def test_invalid_group_s_code_length(self):
        """Test invalid Group S code length (Belgium)"""
        with self.assertRaises(ValidationError):
            self.contract.write({'group_s_code': '12345'})

    def test_unique_group_s_code(self):
        """Test Group S code uniqueness within the same company"""
        with self.assertRaises(ValidationError):
            self.env['hr.employee'].create({
                'name': 'Duplicate Group S Code Contract',
                'date_version': '2020-01-01',
                'company_id': self.company.id,
                'wage': 3000,
                'group_s_code': '123456',
                'country_code': 'BE',
            })

    def test_group_s_code_in_different_company(self):
        """Test the same Group S code in a different company"""
        other_company = self.env['res.company'].create({
            'name': 'Other Company',
            'country_id': self.belgium.id,
        })
        other_employee = self.env['hr.employee'].create({
            'name': 'Contract in Other Company',
            'company_id': other_company.id,
            'wage': 2000,
            'group_s_code': '123456',
            'country_code': 'BE',
        })
        self.assertEqual(other_employee.group_s_code, '123456', "Group S code should be valid in a different company.")

    def test_export_to_group_s_with_no_group_s_code_in_company(self):
        """Test export to Group S with no Group S code in the company"""
        with self.assertRaises(RedirectWarning):
            self.env['l10n.be.hr.payroll.export.group.s'].with_company(
                self.company.id).create({}).action_export_file()

    def test_full_group_s_export_flow(self):
        """Test creating a Group S export, populating, and generating the export file without errors"""
        self.company.group_s_code = '654321'

        work_entry = self.env['hr.work.entry'].create({
            'name': 'Extra',
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'work_entry_type_id': self.work_entry_type.id,
            'date': datetime(2024, 10, 1, 0, 0, 0),
            'duration': 7,
        })
        work_entry.action_validate()

        self.employee.update({
            'contract_date_start': datetime(2024, 10, 1, 0, 0, 0),
            'group_s_code': '654320',
            'schedule_pay': 'monthly',
        })

        export = self.env['l10n.be.hr.payroll.export.group.s'].with_company(self.company.id).create({
            'company_id': self.company.id,
            'reference_month': '10',
            'reference_year': '2024',
        })
        export.action_populate()

        self.assertTrue(export.eligible_employee_line_ids)
        self.assertIn(self.employee, export.eligible_employee_line_ids.employee_id)

        export.action_export_file()
        self.assertTrue(export.export_file)
