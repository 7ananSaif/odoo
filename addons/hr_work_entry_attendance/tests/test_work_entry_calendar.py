# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.hr_work_entry_attendance.tests.common import HrWorkEntryAttendanceCommon
from datetime import datetime, date
from odoo.tests import tagged
from odoo import Command


@tagged('-at_install', 'post_install', 'work_entry_overtime')
class TestPayslipOvertime(HrWorkEntryAttendanceCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contract.write({
            'work_entry_source': "calendar",
            'overtime_from_attendance': True,
        })
        cls.employee.tz = 'Europe/Brussels'
        cls.employee.resource_id.tz = 'Europe/Brussels'
        cls.attendance_type = cls.env.ref('hr_work_entry.work_entry_type_attendance')
        cls.overtime_type = cls.env.ref('hr_work_entry.work_entry_type_overtime')
        cls.work_entry_type_public_type_off = cls.env['hr.work.entry.type'].create({
            'name': 'Public Time Off',
            'code': 'PUBLIC',
            'is_leave': True,
        })

        cls.overtime_ruleset = cls.env['hr.attendance.overtime.ruleset'].create({
            'name': "Overtime Ruleset",
            'rate_combination_mode': 'max',
            'rule_ids': [Command.create({
                'name': "Overtime after 8h/day",
                'base_off': 'quantity',
                'quantity_period': 'day',
                'expected_hours_from_contract': True,
                'work_entry_type_id': cls.overtime_type.id,
                'expected_hours': 8.0,
                'paid': True,
                'amount_rate': 1.5,
            })],
        })

    def _check_work_entry(self, entry, expected_date, expected_duration, expected_type):
        self.assertEqual(entry.date, expected_date)
        self.assertEqual(entry.duration, expected_duration)
        self.assertEqual(entry.work_entry_type_id, expected_type)

    def _check_work_entries(self, entries, expected_values_list):
        self.assertEqual(len(entries), len(expected_values_list))
        for entry, expected_values in zip(entries, expected_values_list):
            self._check_work_entry(entry, *expected_values)

    def test_01_no_overtime(self):
        work_entries = self.contract.generate_work_entries(date(2022, 12, 12), date(2022, 12, 12)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, [
            (date(2022, 12, 12), 8, self.attendance_type),
        ])

    def _test_02_overtime_classic_day_before_after(self, ruleset, expected_work_entries_values):
        self.contract.ruleset_id = ruleset
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 12, 6),
            'check_out': datetime(2022, 12, 12, 20),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 12), date(2022, 12, 12)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, expected_work_entries_values)

    def test_02_overtime_classic_day_before_after(self):
        self._test_02_overtime_classic_day_before_after(self.ruleset, [
            (date(2022, 12, 12), 8, self.attendance_type),
            (date(2022, 12, 12), 5, self.overtime_type),
        ])

    def test_02bis_overtime_classic_day_before_after(self):
        self._test_02_overtime_classic_day_before_after(False, [
            (date(2022, 12, 12), 8, self.attendance_type),
        ])

    def _test_03_overtime_classic_day_before(self, ruleset, expected_work_entries_values):
        self.contract.ruleset_id = ruleset
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 12, 6),
            'check_out': datetime(2022, 12, 12, 16),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 12), date(2022, 12, 12)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, expected_work_entries_values)

    def test_03_overtime_classic_day_before(self):
        self._test_03_overtime_classic_day_before(self.ruleset, [
            (date(2022, 12, 12), 8, self.attendance_type),
            (date(2022, 12, 12), 1, self.overtime_type),
        ])

    def test_03bis_overtime_classic_day_before(self):
        self._test_03_overtime_classic_day_before(False, [
            (date(2022, 12, 12), 8, self.attendance_type),
        ])

    def _test_04_overtime_classic_day_after(self, ruleset, expected_work_entries_values):
        self.contract.ruleset_id = ruleset
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 12, 10),
            'check_out': datetime(2022, 12, 12, 20),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 12), date(2022, 12, 12)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, expected_work_entries_values)

    def test_04_overtime_classic_day_after(self):
        self._test_04_overtime_classic_day_after(self.ruleset, [
            (date(2022, 12, 12), 8, self.attendance_type),
            (date(2022, 12, 12), 1, self.overtime_type),
        ])

    def test_04bis_overtime_classic_day_after(self):
        self._test_04_overtime_classic_day_after(False, [
            (date(2022, 12, 12), 8, self.attendance_type),
        ])

    def test_05_overtime_week_end(self):
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 10, 11),
            'check_out': datetime(2022, 12, 10, 17),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 10), date(2022, 12, 10)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, [
            (date(2022, 12, 10), 6, self.overtime_type),
        ])

    def test_06_no_overtime_public_time_off_whole_day(self):
        self.env['resource.calendar.leaves'].create([{
            'name': "Public Time Off",
            'calendar_id': False,
            'company_id': self.env.company.id,
            'resource_id': False,
            'date_from': datetime(2022, 12, 26, 0, 0, 0),
            'date_to': datetime(2022, 12, 26, 23, 59, 59),
            'time_type': "leave",
            'work_entry_type_id': self.work_entry_type_public_type_off.id,
        }])
        work_entries = self.contract.generate_work_entries(date(2022, 12, 26), date(2022, 12, 26)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, [
            (date(2022, 12, 26), 8, self.work_entry_type_public_type_off),
        ])

    def _test_07_overtime_public_time_off_whole_day(self, ruleset, expected_work_entries_values):
        self.env['resource.calendar.leaves'].create([{
            'name': "Public Time Off",
            'company_id': self.env.company.id,
            'resource_id': False,
            'date_from': datetime(2022, 12, 25, 23, 0, 0),
            'date_to': datetime(2022, 12, 26, 22, 59, 59),
            'time_type': "leave",
            'work_entry_type_id': self.work_entry_type_public_type_off.id,
        }])
        self.contract.ruleset_id = ruleset
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 26, 6),
            'check_out': datetime(2022, 12, 26, 20),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 26), date(2022, 12, 26)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, expected_work_entries_values)

    def test_07_overtime_public_time_off_whole_day(self):
        ruleset = self.env['hr.attendance.overtime.ruleset'].create({
                'name': 'Ruleset schedule quantity',
                'rule_ids': [
                    (0, 0, {
                        'name': 'Rule schedule quantity',
                        'base_off': 'quantity',
                        'expected_hours_from_contract': True,
                        'quantity_period': 'day',
                    }),
                    (0, 0, {
                        'name': 'Rule employee is off',
                        'base_off': 'timing',
                        'timing_type': 'leave',
                    }),
                ],
            })
        self._test_07_overtime_public_time_off_whole_day(ruleset, [
            (date(2022, 12, 26), 14, self.overtime_type),  # 9h from the rule employee is off and 5h from the rules schedule quantity and employee is off
            (date(2022, 12, 26), 8, self.work_entry_type_public_type_off),
        ])

    def test_07bis2_overtime_public_time_off_whole_day(self):
        ruleset = self.env['hr.attendance.overtime.ruleset'].create({
                'name': 'Ruleset schedule quantity',
                'rule_ids': [
                    (0, 0, {
                        'name': 'Rule schedule quantity',
                        'base_off': 'quantity',
                        'expected_hours_from_contract': True,
                        'quantity_period': 'day',
                    }),
                ],
            })
        self._test_07_overtime_public_time_off_whole_day(ruleset, [
            (date(2022, 12, 26), 5, self.overtime_type),
            (date(2022, 12, 26), 8, self.work_entry_type_public_type_off),
        ])

    def test_07bis_overtime_public_time_off_whole_day(self):
        self._test_07_overtime_public_time_off_whole_day(False, [
            (date(2022, 12, 26), 8, self.work_entry_type_public_type_off),
        ])

    def _test_08_overtime_public_time_off_half_day(self, ruleset, expected_work_entries_values):
        self.contract.ruleset_id = ruleset
        self.env['resource.calendar.leaves'].create([{
            'name': "Public Time Off",
            'calendar_id': False,
            'company_id': self.env.company.id,
            'resource_id': False,
            'date_from': datetime(2022, 12, 26, 0, 0, 0),
            'date_to': datetime(2022, 12, 26, 23, 59, 59),
            'time_type': "leave",
            'work_entry_type_id': self.work_entry_type_public_type_off.id,
        }])
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 26, 6),
            'check_out': datetime(2022, 12, 26, 11),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 26), date(2022, 12, 26)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, expected_work_entries_values)

    def test_08_overtime_public_time_off_half_day(self):
        self._test_08_overtime_public_time_off_half_day(self.ruleset, [
            (date(2022, 12, 26), 8, self.work_entry_type_public_type_off),
        ])

    def test_08bis_overtime_public_time_off_half_day(self):
        self._test_08_overtime_public_time_off_half_day(False, [
            (date(2022, 12, 26), 8, self.work_entry_type_public_type_off),
        ])

    def _test_09_overtime_public_time_off_1_hour(self, ruleset, expected_work_entries_values):
        self.contract.ruleset_id = ruleset
        self.env['resource.calendar.leaves'].create([{
            'name': "Public Time Off",
            'calendar_id': False,
            'company_id': self.env.company.id,
            'resource_id': False,
            'date_from': datetime(2022, 12, 26, 0, 0, 0),
            'date_to': datetime(2022, 12, 26, 23, 59, 59),
            'time_type': "leave",
            'work_entry_type_id': self.work_entry_type_public_type_off.id,
        }])
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 26, 10),
            'check_out': datetime(2022, 12, 26, 11),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 26), date(2022, 12, 26)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, expected_work_entries_values)

    def test_09_overtime_public_time_off_1_hour(self):
        self._test_09_overtime_public_time_off_1_hour(self.ruleset, [
            (date(2022, 12, 26), 8, self.work_entry_type_public_type_off),
        ])

    def test_09bis_overtime_public_time_off_1_hour(self):
        self._test_09_overtime_public_time_off_1_hour(False, [
            (date(2022, 12, 26), 8, self.work_entry_type_public_type_off),
        ])

    def _test_10_overtime_public_time_off_1_hour_inside(self, ruleset, expected_work_entries_values):
        self.contract.ruleset_id = ruleset
        self.env['resource.calendar.leaves'].create([{
            'name': "Public Time Off",
            'calendar_id': False,
            'company_id': self.env.company.id,
            'resource_id': False,
            'date_from': datetime(2022, 12, 26, 0, 0, 0),
            'date_to': datetime(2022, 12, 26, 23, 59, 59),
            'time_type': "leave",
            'work_entry_type_id': self.work_entry_type_public_type_off.id,
        }])
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 26, 9),
            'check_out': datetime(2022, 12, 26, 10),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 26), date(2022, 12, 26)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, expected_work_entries_values)

    def test_10_overtime_public_time_off_1_hour_inside(self):
        self._test_10_overtime_public_time_off_1_hour_inside(self.ruleset, [
            (date(2022, 12, 26), 8, self.work_entry_type_public_type_off),
        ])

    def test_10bis_overtime_public_time_off_1_hour_inside(self):
        self._test_10_overtime_public_time_off_1_hour_inside(False, [
            (date(2022, 12, 26), 8, self.work_entry_type_public_type_off),
        ])

    def test_11_overtime_classic_day_under_threshold(self):
        self.contract.company_id.overtime_company_threshold = 15
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 12, 15),
            'check_out': datetime(2022, 12, 12, 16, 13),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 12), date(2022, 12, 12)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, [
            (date(2022, 12, 12), 8, self.attendance_type),
        ])

    def _test_12_overtime_classic_day_below_threshold(self, ruleset, expected_work_entries_values):
        self.contract.ruleset_id = ruleset
        self.contract.company_id.overtime_company_threshold = 15
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 12, 15),
            'check_out': datetime(2022, 12, 12, 16, 18),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 12), date(2022, 12, 12)).sorted('work_entry_type_id')
        self._check_work_entries(work_entries, expected_work_entries_values)

    def test_12_overtime_classic_day_below_threshold(self):
        self._test_12_overtime_classic_day_below_threshold(self.ruleset, [
            (date(2022, 12, 12), 8, self.attendance_type),
        ])

    def test_12bis_overtime_classic_day_below_threshold(self):
        self._test_12_overtime_classic_day_below_threshold(False, [
            (date(2022, 12, 12), 8, self.attendance_type),
        ])

    def test_13_overtime_approval(self):
        self.contract.company_id.write({'attendance_overtime_validation': 'by_manager'})
        self.contract.ruleset_id = self.overtime_ruleset
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 26, 5),
            'check_out': datetime(2022, 12, 26, 20),
        })
        work_entries = self.contract.generate_work_entries(date(2022, 12, 26), date(2022, 12, 26))
        self.assertEqual(1, len(work_entries))
        self.assertEqual('Attendance', work_entries.work_entry_type_id.name)
        overtime_line = self.env['hr.attendance.overtime.line'].search([('employee_id', '=', self.employee.id)])
        self.assertEqual(1, len(overtime_line))
        self.assertEqual('to_approve', overtime_line.status)
        overtime_line.action_approve()
        self.assertEqual('approved', overtime_line.status)
        work_entries = self.env['hr.work.entry'].search([('employee_id', '=', self.employee.id)])
        self.assertEqual(2, len(work_entries))
        self.assertTrue(any(we.work_entry_type_id == self.overtime_type for we in work_entries))

        overtime_line.action_refuse()
        self.assertEqual(1, len(overtime_line))
        self.assertEqual('refused', overtime_line.status)
        work_entries = self.env['hr.work.entry'].search([('employee_id', '=', self.employee.id)])
        self.assertEqual(1, len(work_entries))
        self.assertFalse(any(we.work_entry_type_id == self.overtime_type for we in work_entries))

    def test_overtime_on_multiple_attendances(self):
        self.contract.write({
            'work_entry_source': "attendance",
            'ruleset_id': self.ruleset,
        })
        first_attendance = self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 1, 7, 30),
            'check_out': datetime(2022, 12, 1, 12, 30),
        })
        self.assertFalse(first_attendance.linked_overtime_ids)

        second_attendance = self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 1, 12, 30),
            'check_out': datetime(2022, 12, 1, 18, 30),
        })
        self.assertEqual(second_attendance.linked_overtime_ids.duration, 2)

        third_attendance = self.env['hr.attendance'].new({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 12, 1, 18, 30),
            'check_out': datetime(2022, 12, 1, 20, 30),
        })
        third_attendance = self.env['hr.attendance'].create(third_attendance._convert_to_write(third_attendance._cache))
        self.assertEqual(third_attendance.linked_overtime_ids.duration, 2)
