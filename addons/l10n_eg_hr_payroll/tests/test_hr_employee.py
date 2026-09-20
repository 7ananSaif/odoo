# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo.tests import tagged, TransactionCase

from freezegun import freeze_time


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEgyptianHrEmployee(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.egyptian_company = cls.env['res.company'].create({
            'name': 'Egyptian Company',
            'country_id': cls.env.ref('base.eg').id,
            'currency_id': cls.env.ref('base.EGP').id,
        })
        cls.leave_type = cls.env['hr.leave.type'].create({
            'name': 'Annual Leave',
            'requires_allocation': 'yes',
            'company_id': cls.egyptian_company.id,
        })
        cls.egyptian_company.l10n_eg_annual_leave_type_id = cls.leave_type
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'EG Sun-Thu',
            'attendance_ids': [
                (0, 0, {'name': 'Sun', 'dayofweek': '6', 'hour_from': 8, 'hour_to': 16}),
                (0, 0, {'name': 'Mon', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 16}),
                (0, 0, {'name': 'Tue', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 16}),
                (0, 0, {'name': 'Wed', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 16}),
                (0, 0, {'name': 'Thu', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 16}),
            ],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'company_id': cls.egyptian_company.id,
            'resource_calendar_id': cls.calendar.id,
        })

    @freeze_time("2025-12-31")
    def test_get_annual_remaining_leaves(self):
        result = self.employee._l10n_eg_get_annual_remaining_leaves()
        self.assertIsInstance(result, dict)
        self.assertIn(self.employee.id, result)
        self.assertEqual(result[self.employee.id], 0, "The employee has no allocation yet so the result should be 0")

        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Annual Leave Allocation 2025',
            'holiday_status_id': self.leave_type.id,
            'number_of_days': 25,
            'employee_id': self.employee.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 12, 31),
        })
        allocation._action_validate()
        result = self.employee._l10n_eg_get_annual_remaining_leaves()
        self.assertEqual(result[self.employee.id], 25, "the employee has an allocation of 25 days so the result should be 25")

        leave = self.env['hr.leave'].create({
            'name': 'Annual Leave Request',
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee.id,
            'request_date_from': date(2025, 8, 24),
            'request_date_to': date(2025, 8, 31),
            'request_unit_half': False,
            'request_unit_hours': False,
        })
        leave._action_validate()
        result = self.employee._l10n_eg_get_annual_remaining_leaves()
        self.assertEqual(result[self.employee.id], 19, "the employee has an allocation and a leave so the result should be 25 - 6 = 19")
