# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install', 'work_entry_reset')
class TestWorkEntryReset(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Richard',
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'wage': 5000,
        })
        cls.employee.version_id.generate_work_entries(
            date(2025, 1, 1),
            date(2025, 1, 31)
        )
        cls.payslip = cls.env['hr.payslip'].create({
            'name': 'Test Payslip',
            'employee_id': cls.employee.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
        })

    def test_work_entry_reset_from_payslip(self):
        self.start_tour("/odoo/payslips", 'hr_payroll_work_entry_reset_tour', login='admin')
