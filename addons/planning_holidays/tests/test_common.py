# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from odoo.addons.planning.tests.common import TestCommonPlanning

class TestCommon(TestCommonPlanning):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpEmployees()
        cls.setUpDates()

        cls.env.user.tz = 'Europe/Brussels'
        cls.calendar, cls.flexible_calendar = cls.env['resource.calendar'].create([{
            'name': 'Calendar',
        }, {
            'name': 'Flex Calendar',
            'tz': 'UTC',
            'flexible_hours': True,
            'hours_per_day': 8,
            'full_time_required_hours': 40,
            'attendance_ids': [],
        }])
        cls.env.company.resource_calendar_id = cls.calendar

        # Leave type
        cls.leave_type = cls.env['hr.leave.type'].create({
            'name': 'time off',
            'requires_allocation': False,
            'request_unit': 'hour',
        })

        # Allocations
        cls.allocation_bert = cls.env['hr.leave.allocation'].create({
            'state': 'confirm',
            'holiday_status_id': cls.leave_type.id,
            'employee_id': cls.employee_bert.id,
            'date_from': time.strftime('%Y-01-01'),
            'date_to': time.strftime('%Y-12-31'),
        })
        cls.allocation_bert.action_approve()
        cls.flex_role = cls.env['planning.role'].create({'name': 'flex role'})
