# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo.tests import tagged
from odoo.exceptions import UserError

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestConsecutiveLeaves(TestPayrollCommon):
    def setUp(self):
        super().setUp()
        self.employee = self.env['hr.employee'].create({
            'name': 'Employee',
            'resource_calendar_id': self.resource_calendar.id
        })
        self.leave_type = self.env['hr.leave.type'].create({
            'name': 'Sick Leave without Certificate',
            'requires_allocation': False,
            'l10n_be_no_consecutive_leaves_allowed': True
        })

    def test_no_consecutive_leaves_allowed_directly_before(self):
        """
        Test that an employee can't take a leave directly before another leave of the same type
        """
        first_leave = self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.leave_type.id,
            'request_date_from': date(2023, 1, 4),
            'request_date_to': date(2023, 1, 4),
        })
        first_leave.action_approve()

        second_leave = self.env['hr.leave'].create({
                'employee_id': self.employee.id,
                'holiday_status_id': self.leave_type.id,
                'request_date_from': date(2023, 1, 3),
                'request_date_to': date(2023, 1, 3),
            })

        with self.assertRaises(UserError):
            second_leave.action_approve()

    def test_no_consecutive_leaves_allowed_directly_after(self):
        """
        Test that an employee can't take a leave directly after another leave of the same type
        """
        first_leave = self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.leave_type.id,
            'request_date_from': date(2023, 1, 4),
            'request_date_to': date(2023, 1, 4),
        })
        first_leave.action_approve()

        second_leave = self.env['hr.leave'].create({
                'employee_id': self.employee.id,
                'holiday_status_id': self.leave_type.id,
                'request_date_from': date(2023, 1, 5),
                'request_date_to': date(2023, 1, 5),
            })

        with self.assertRaises(UserError):
            second_leave.action_approve()

    def test_no_consecutive_leaves_allowed_allow_with_gap(self):
        """
        Test that an employee can take a leave with a gap between the two leaves
        """
        first_leave = self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.leave_type.id,
            'request_date_from': date(2023, 1, 4),
            'request_date_to': date(2023, 1, 4),
        })
        first_leave.action_approve()

        second_leave = self.env['hr.leave'].create({
                'employee_id': self.employee.id,
                'holiday_status_id': self.leave_type.id,
                'request_date_from': date(2023, 1, 6),
                'request_date_to': date(2023, 1, 6),
            })

        second_leave.action_approve()  # no error should be raised

    def test_no_consecutive_leaves_allowed_with_weekend(self):
        """
        Test that an employee can't take a leave with a weekend between the two leaves
        """
        first_leave = self.env['hr.leave'].create({
                'employee_id': self.employee.id,
                'holiday_status_id': self.leave_type.id,
                'request_date_from': date(2023, 1, 6),
                'request_date_to': date(2023, 1, 6),
            })
        first_leave.action_approve()

        second_leave = self.env['hr.leave'].create({
                'employee_id': self.employee.id,
                'holiday_status_id': self.leave_type.id,
                'request_date_from': date(2023, 1, 9),
                'request_date_to': date(2023, 1, 9),
            })

        with self.assertRaises(UserError):
            # This leave is considered consecutive to the previous one
            # as there is no working day between the two leaves
            second_leave.action_approve()

    def test_no_consecutive_leaves_allowed_with_public_holiday(self):
        """
        Test that an employee can't take a leave with a public holiday between the two leaves
        """
        # public holiday
        self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday',
            'date_from': datetime(2023, 1, 18, 0, 0, 0),
            'date_to': datetime(2023, 1, 18, 23, 59, 59),
            'resource_id': False,
            'calendar_id': self.employee.resource_calendar_id.id
        })

        first_leave = self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.leave_type.id,
            'request_date_from': date(2023, 1, 19),
            'request_date_to': date(2023, 1, 19),
        })
        first_leave.action_approve()  # no error should be raised

        second_leave = self.env['hr.leave'].create({
                'employee_id': self.employee.id,
                'holiday_status_id': self.leave_type.id,
                'request_date_from': date(2023, 1, 17),
                'request_date_to': date(2023, 1, 17),
            })

        with self.assertRaises(UserError):
            # This leave is considered consecutive to the previous one
            # as there is just a public holiday between the two leaves
            second_leave.action_approve()
