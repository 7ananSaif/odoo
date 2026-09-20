# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, rrule

from odoo import Command
from odoo.tests.common import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'work_entry_attendance_perf')
class TestHrWorkEntryAttendancePerformance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.company_id = cls.env['res.company'].create({'name': 'Flower Corporation'})

        cls.work_entry_type_overtime = cls.env.ref('hr_work_entry.work_entry_type_overtime')

        cls.ruleset = cls.env['hr.attendance.overtime.ruleset'].create({
            'name': 'Ruleset schedule quantity',
            'rule_ids': [Command.create({
                    'name': 'Rule schedule quantity',
                    'base_off': 'quantity',
                    'expected_hours_from_contract': True,
                    'quantity_period': 'day',
                    'work_entry_type_id': cls.work_entry_type_overtime.id,
                })],
        })

        employees = cls.env['hr.employee'].create([{
            'name': f'Employee {i}',
            'sex': 'male',
            'birthday': '1982-08-01',
            'country_id': cls.env.ref('base.us').id,
            'wage': 5000.0,
            'date_version': date.today() - relativedelta(months=2),
            'contract_date_start': date.today() - relativedelta(months=2),
            'work_entry_source': 'attendance',
            'contract_date_end': False,
            'ruleset_id': cls.ruleset.id,
        } for i in range(100)])
        for employee in employees:
            employee.create_version({'date_version': date.today() - relativedelta(months=1, days=15), 'wage': 5500})
            employee.create_version({'date_version': date.today() - relativedelta(months=1), 'wage': 6000})

        vals = []
        for employee in employees:
            for day in rrule(DAILY, dtstart=date.today() - relativedelta(months=2), until=date.today()):
                vals.append({
                    'employee_id': employee.id,
                    'check_in': day.strftime('%Y-%m-%d 08:00:%S'),
                    'check_out': day.strftime('%Y-%m-%d 16:36:%S'),
                })
        cls.attendances = cls.env['hr.attendance'].create(vals)

    def test_regenerate_work_entries(self):

        with self.profile():
            with self.assertQueryCount(1081):
                slots = [{'date': attendance.date, 'employee_id': attendance.employee_id.id} for attendance in self.attendances]
                self.env["hr.work.entry.regeneration.wizard"].regenerate_work_entries(slots=slots)
