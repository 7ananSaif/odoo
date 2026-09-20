# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.hr_work_entry_attendance.tests.common import HrWorkEntryAttendanceCommon
from odoo import Command

from datetime import datetime, date

from odoo.tests import tagged

@tagged('-at_install', 'post_install', 'payslip_overtime')
class TestPayslipOvertime(HrWorkEntryAttendanceCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.struct_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test Structure Type',
            'wage_type': 'hourly',
        })
        cls.struct = cls.env['hr.payroll.structure'].create({
            'name': 'Test Structure - Worker',
            'type_id': cls.struct_type.id,
        })
        cls.payslip = cls.env['hr.payslip'].create({
            'name': 'Test Payslip',
            'employee_id': cls.employee.id,
            'struct_id': cls.struct.id,
            'date_from': '2022-01-01',
            'date_to': '2022-01-31',
        })
        cls.ruleset = cls.env['hr.attendance.overtime.ruleset'].create({
            'name': 'Ruleset schedule quantity',
            'rule_ids': [Command.create({
                    'name': 'Rule schedule quantity',
                    'base_off': 'quantity',
                    'expected_hours_from_contract': True,
                    'quantity_period': 'day',
                })],
        })

        cls.contract.structure_type_id = cls.struct_type
        cls.contract.hourly_wage = 100
        cls.contract.overtime_from_attendance = True
        cls.contract.ruleset_id = cls.ruleset
        cls.company = cls.payslip.company_id
        
    def test_overtime_outside_period(self):
        # Right before the payslip period
        self.env['hr.attendance.overtime.line'].create({
            'employee_id': self.employee.id,
            'date': date(2021, 12, 31),
            'duration': 5,
        })
        # Right after the payslip period
        self.env['hr.attendance.overtime.line'].create({
            'employee_id': self.employee.id,
            'date': date(2022, 2, 1),
            'duration': 5,
        })
        # Since contract resource_calendar_id's default to the company's,
        # we can just change the company's resource_calendar_id's timezone.
        self.env.company.resource_calendar_id.tz = "Asia/Manila"
        self.payslip._compute_worked_days_line_ids()
        self.assertFalse(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == 'OVERTIME'))
        self.env.company.resource_calendar_id.tz = "Indian/Maldives"
        self.payslip._compute_worked_days_line_ids()
        self.assertFalse(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == 'OVERTIME'))
        self.env.company.resource_calendar_id.tz = "Europe/Brussels"
        self.payslip._compute_worked_days_line_ids()
        self.assertFalse(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == 'OVERTIME'))

    def test_with_overtime(self):
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 1, 3, 0, 0, 0),
            'check_out': datetime(2022, 1, 3, 20, 0, 0),
        })
        self.payslip._compute_worked_days_line_ids()
        self.assertEqual(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == 'OVERTIME').number_of_hours, 11)

    def test_with_negative_overtime(self):
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 1, 3, 9, 0, 0),
            'check_out': datetime(2022, 1, 3, 12, 0, 0),
        })
        self.payslip._compute_worked_days_line_ids()
        self.assertFalse(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == 'OVERTIME'))

    def test_with_overtime_calendar_contract(self):
        self.contract.work_entry_source = 'calendar'
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 1, 3, 0, 0, 0),
            'check_out': datetime(2022, 1, 3, 20, 0, 0),
        })
        self.payslip._compute_worked_days_line_ids()
        self.assertEqual(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == 'OVERTIME').number_of_hours, 11)

    def test_overtime_with_approval(self):
        """Test that the overtime is taken into account only when it's approved."""
        self.company.write({
            "attendance_overtime_validation": "by_manager"
        })

        attendance = self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 1, 3, 0, 0, 0),
            'check_out': datetime(2022, 1, 3, 20, 0, 0),
        })
        self.payslip._compute_worked_days_line_ids()
        self.assertFalse(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == 'OVERTIME'))

        # Approve the overtime
        attendance.action_approve_overtime()
        self.payslip.version_id.generate_work_entries(self.payslip.date_from, self.payslip.date_to, force=True)
        self.payslip._compute_worked_days_line_ids()
        self.assertTrue(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == 'OVERTIME'))
