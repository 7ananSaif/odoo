# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged
from odoo.exceptions import ValidationError

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_credit_time')
class TestPayrollCreditTime(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super(TestPayrollCreditTime, cls).setUpClass()

        cls.paid_time_off_type = cls.holiday_leave_types  # cls.holiday_leave_types.filtered(lambda leave_type: leave_type.validity_start == date(2023, 1, 1) and leave_type.validity_stop == date(2023, 12, 31))

        cls.wizard = cls.env['hr.payroll.alloc.paid.leave'].create({
            'year': 2022,
            'holiday_status_id': cls.paid_time_off_type.id
        })
        cls.wizard.alloc_employee_ids = cls.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id in [cls.employee_georges.id, cls.employee_john.id, cls.employee_a.id])

        with freeze_time('2023-12-31'):
            view = cls.wizard.generate_allocation()
        cls.allocations = cls.env['hr.leave.allocation'].search(view['domain'])
        for allocation in cls.allocations:
            allocation.action_approve()

    def test_credit_time_for_georges(self):
        """
        Test Case:
        The employee Georges asks a credit time to work at mid-time (3 days/week) from 01/02 to 30/04 in the current year,
        normally, he has 14.5 days before his credit and with the credit, the number of paid time off days decreases to
        10 days. If Georges didn't take some leaves during his credit, when he exists it, his number of paid time off
        days increase to the number of days he had before.
        """

        georges_current_contract = self.georges_contracts[-1]
        georges_allocation = self.allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_georges.id)
        self.assertEqual(georges_allocation.number_of_days, 14.5)

        # Test for employee Georges
        # Credit time for Georges
        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=georges_current_contract.id).new({
            'date_start': date(2023, 2, 1),
            'date_end': date(2023, 4, 30),
            'resource_calendar_id': self.resource_calendar_mid_time.id,
            'leave_type_id': self.paid_time_off_type.id,
            'previous_contract_creation': True,
        })
        self.assertEqual(wizard.time_off_allocation, 10)
        self.assertAlmostEqual(wizard.work_time_rate, 50, 2)
        self.assertEqual(wizard.leave_allocation_id.id, georges_allocation.id)
        wizard.with_context(force_schedule=True).action_validate()

        # Apply allocation changes directly
        self.assertEqual(georges_allocation.number_of_days, 14.5)
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2023, 2, 1))
        self.assertEqual(georges_allocation.number_of_days, 10)

        # Apply allocation changes directly - Credit time exit
        full_time_contract = self.employee_georges.version_ids[-1]
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(full_time_contract.contract_date_start)
        self.assertEqual(georges_allocation.number_of_days, 14.5)

    def test_credit_time_for_john_doe(self):
        """
        Test Case:
        The employee John Doe asks a credit time to work at 9/10 from 01/02 to 30/04 in the current year.
        """
        john_current_contract = self.john_contracts[-1]
        john_allocation = self.allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_john.id)
        self.assertEqual(john_allocation.number_of_days, 10)

        # Test for employee John Doe
        # Credit time for John Doe
        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=john_current_contract.id).new({
            'date_start': date(2023, 2, 1),
            'date_end': date(2023, 4, 30),
            'resource_calendar_id': self.resource_calendar_9_10.id,
            'leave_type_id': self.paid_time_off_type.id,
            'previous_contract_creation': True,
        })
        self.assertEqual(wizard.time_off_allocation, 16)  # John may have 88% of 20 days this year -> ~17.5
        self.assertAlmostEqual(wizard.work_time_rate, 90, 2)
        self.assertEqual(wizard.leave_allocation_id.id, john_allocation.id)
        wizard.with_context(force_schedule=True).action_validate()

        # Apply allocation changes directly
        self.assertEqual(john_allocation.number_of_days, 10)
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2023, 2, 1))
        self.assertEqual(john_allocation.number_of_days, 16)

        # Apply allocation changes directly - Credit time exit
        continuation_contract = self.employee_john.version_ids[-1]
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(continuation_contract.contract_date_start)
        self.assertEqual(john_allocation.number_of_days, 10)

    def test_credit_time_for_a(self):
        """
        Test Case:
        The employee A has a contract full-time from 01/01 of the previous year.
        Then, he has right to 20 complete days as paid time off.
        The employee A asks a credit time to work at 4/5 (4 days/week) from 01/02 to 30/04 in the current year.
        With this credit time, his number of paid time off days decrease to 16.
        """
        a_current_contract = self.a_contracts[-1]
        a_allocation = self.allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_a.id)

        # Test for employee A
        # Credit time for A
        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=a_current_contract.id).new({
            'date_start': date(2023, 2, 1),
            'date_end': date(2023, 4, 30),
            'resource_calendar_id': self.resource_calendar_4_5.id,
            'leave_type_id': self.paid_time_off_type.id,
            'previous_contract_creation': True,
        })
        self.assertEqual(wizard.time_off_allocation, 16)
        self.assertAlmostEqual(wizard.work_time_rate, 80, 2)
        wizard.with_context(force_schedule=True).action_validate()

        self.assertEqual(a_allocation.number_of_days, 20)
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2023, 2, 1))
        self.assertEqual(a_allocation.number_of_days, 16)

        # Apply allocation changes directly
        full_time_contract = self.employee_a.version_ids[-1]
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(full_time_contract.contract_date_start)
        self.assertEqual(a_allocation.number_of_days, 20)

    def test_remaining_leaves_with_credit_time(self):
        """
        Test Case (only with the employee A)
        - Full Time 01/01 -> 31/05:
            A has an allocation for 20 days.
            A took 6 days off (14 leaves remaining on 20 max).
        - 4/5 (4 days/week) 01/06 -> 31/08:
            A has an allocation for 16 days (20 * 4 / 5 = 16).
            A took 6 days off (4 leaves remaining on 16 max).
        - 1/2 (3 days/week) 01/09 -> 31/12:
            A has an allocation for 12 days (max(leaves taken = 12, 20 * 1 / 2 = 10)).
            A cannot take any more days (0 leaves remaining on 12 max).
        """
        a_current_contract = self.a_contracts[-1]
        a_allocation = self.allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_a.id)
        self.assertEqual(a_allocation.number_of_days, 20)

        taken_leaves = 0
        # leaves don't count if theyre planned in the future, they have to actually be taken
        with freeze_time(date(2023, 2, 1)):
            leave = self.env['hr.leave'].create({
                'holiday_status_id': self.paid_time_off_type.id,
                'employee_id': self.employee_a.id,
                'request_date_from': date(2023, 2, 1),
                'request_date_to': date(2023, 2, 8),
            })
            leave.action_approve()
            taken_leaves += leave.number_of_days
            self.assertEqual(taken_leaves, 6)

            # Credit time
            wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=a_current_contract.id).new({
                'date_start': date(2023, 6, 1),
                'resource_calendar_id': self.resource_calendar_4_5.id,
                'leave_type_id': self.paid_time_off_type.id,
                'previous_contract_creation': True,
            })
            self.assertEqual(wizard.time_off_allocation, 16)  # 16 max
            self.assertAlmostEqual(wizard.work_time_rate, 80, 2)
            wizard.with_context(force_schedule=True).action_validate()

            # Apply allocation changes directly
            self.assertEqual(a_allocation.number_of_days, 20)
            self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2023, 6, 1))
            self.assertEqual(a_allocation.number_of_days, 16)

        with freeze_time(date(2023, 7, 1)):
            leave = self.env['hr.leave'].create({
                'holiday_status_id': self.paid_time_off_type.id,
                'employee_id': self.employee_a.id,
                'request_date_from': date(2023, 7, 1),
                'request_date_to': date(2023, 7, 11),
            })
            leave.action_approve()
            taken_leaves += leave.number_of_days
            self.assertEqual(taken_leaves, 12)

            # Credit time
            a_contract_4_5 = self.employee_a.version_ids[-1]
            wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=a_contract_4_5.id).new({
                'date_start': date(2023, 9, 1),
                'date_end': date(2023, 12, 31),
                'resource_calendar_id': self.resource_calendar_mid_time.id,
                'leave_type_id': self.paid_time_off_type.id,
                'previous_contract_creation': True,
            })

            # Should be 10, but since the employee has already taken 12, the allocation keeps those taken days.
            self.assertEqual(wizard.time_off_allocation, 12)
            self.assertAlmostEqual(wizard.work_time_rate, 50, 2)
            wizard.with_context(force_schedule=True).action_validate()

            # Apply allocation changes directly
            self.assertEqual(a_allocation.number_of_days, 16)
            self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2023, 9, 2))
            self.assertEqual(a_allocation.number_of_days, 12)

            # Normally he has already taken all his paid time offs, if he takes another, we should have an error
            with self.assertRaises(ValidationError):
                leave = self.env['hr.leave'].create({
                    'holiday_status_id': self.paid_time_off_type.id,
                    'employee_id': self.employee_a.id,
                    'request_date_from': date(2023, 10, 4),
                    'request_date_to': date(2023, 10, 8),
                })
                leave.action_approve()

            full_time_contract = self.employee_a.version_ids[-1]
            self.assertEqual(a_allocation.number_of_days, 12)
            self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(full_time_contract.contract_date_start)
            self.assertEqual(a_allocation.number_of_days, 15.5)
