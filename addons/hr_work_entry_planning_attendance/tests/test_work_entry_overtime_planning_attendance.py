# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, date

from odoo import Command
from odoo.tests import tagged, TransactionCase, HttpCase


@tagged('-at_install', 'post_install', 'work_entry_overtime')
class HrWorkEntryContractTest(HttpCase, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.country_id = cls.env.ref('base.us')
        cls.env.company.resource_calendar_id.tz = "Europe/Brussels"

        cls.ruleset = cls.env['hr.attendance.overtime.ruleset'].create({
            'name': 'Ruleset schedule quantity',
            'rule_ids': [Command.create({
                    'name': 'Rule schedule quantity',
                    'base_off': 'quantity',
                    'expected_hours_from_contract': True,
                    'quantity_period': 'day',
                })],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Homelander',
            'tz': 'UTC',
            'wage': 35000,
            'work_entry_source': 'planning',
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'overtime_from_attendance': True,
            'ruleset_id': cls.ruleset.id
        })
        cls.contract = cls.employee.version_id
        cls.attendance_type = cls.env.ref('hr_work_entry.work_entry_type_attendance')
        cls.overtime_type = cls.env.ref('hr_work_entry.work_entry_type_overtime')
        cls.slots = cls.env['planning.slot'].create({
            'resource_id': cls.contract.employee_id.resource_id.id,
            'start_datetime': datetime(2024, 7, 16, 8, 0, 0),
            'end_datetime': datetime(2024, 7, 16, 16, 0, 0),
            'state': 'published',
        })

    def test_overtime_work_entry_by_planning(self):
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2024, 7, 16, 8, 0, 0),
            'check_out': datetime(2024, 7, 16, 18, 0, 0),
        })

        work_entries = self.contract.generate_work_entries(date(2024, 7, 1), date(2024, 7, 31)).sorted('work_entry_type_id')
        another_work_entry = self.contract.generate_work_entries(date(2024, 7, 1), date(2024, 7, 31)).sorted('work_entry_type_id')
        self.assertEqual(len(work_entries), 2)
        self.assertEqual(work_entries[0].date, date(2024, 7, 16))
        self.assertEqual(work_entries[0].duration, 7)
        self.assertEqual(work_entries[0].work_entry_type_id, self.attendance_type)
        self.assertEqual(work_entries[1].date, date(2024, 7, 16))
        self.assertEqual(work_entries[1].duration, 2)
        self.assertEqual(work_entries[1].work_entry_type_id, self.overtime_type)

        # should not generate the work entry becuase the work entry for that woking day is already generated
        self.assertFalse(another_work_entry)

    def test_overtime_work_entry_by_planning_bis(self):
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2024, 7, 16, 8, 0, 0),
            'check_out': datetime(2024, 7, 16, 18, 0, 0),
        })
        self.contract.overtime_from_attendance = False

        work_entries = self.contract.generate_work_entries(date(2024, 7, 1), date(2024, 7, 31)).sorted('work_entry_type_id')
        another_work_entry = self.contract.generate_work_entries(date(2024, 7, 1), date(2024, 7, 31)).sorted('work_entry_type_id')
        self.assertEqual(len(work_entries), 1)
        self.assertEqual(work_entries[0].date, date(2024, 7, 16))
        self.assertEqual(work_entries[0].duration, 7)
        self.assertEqual(work_entries[0].work_entry_type_id, self.attendance_type)

        # should not generate the work entry becuase the work entry for that woking day is already generated
        self.assertFalse(another_work_entry)
