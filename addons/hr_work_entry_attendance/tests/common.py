# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from odoo.fields import Date
from odoo.tests import TransactionCase
from odoo import Command


class HrWorkEntryAttendanceCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.country_id = cls.env.ref('base.us')
        cls.env.company.resource_calendar_id.tz = "Europe/Brussels"
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Billy Pointer',
            'tz': 'UTC',
            'wage': 3500,
            'work_entry_source': 'attendance',
            'date_version': '2020-01-01',
            'contract_date_start': '2020-01-01',
        })

        cls.contract = cls.employee.version_id

        cls.work_entry_type_leave = cls.env['hr.work.entry.type'].create({
            'name': 'Time Off',
            'is_leave': True,
            'code': 'LEAVETEST100'
        })
        cls.richard_emp = cls.env['hr.employee'].create({
            'name': 'Richard',
            'sex': 'male',
            'birthday': '1984-05-01',
            'country_id': cls.env.ref('base.us').id,
            'date_version': Date.to_date('2018-01-01'),
            'contract_date_start': Date.to_date('2018-01-01'),
            'contract_date_end': Date.today() + relativedelta(years=2),
            'wage': 5000.33,
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

        cls.employee.ruleset_id = cls.ruleset
        cls.richard_emp.ruleset_id = cls.ruleset
