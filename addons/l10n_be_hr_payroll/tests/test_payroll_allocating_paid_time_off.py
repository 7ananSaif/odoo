# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged
from freezegun import freeze_time

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'alloc_paid_time_off')
class TestPayrollAllocatingPaidTimeOff(TestPayrollCommon):

    def setUp(self):
        super().setUp()

        self.resource_calendar_40_hours = self.resource_calendar.copy({
            'name': 'Test Calendar 40 Hours',
            'hours_per_day': 8,
            'hours_per_week': 40,
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Monday Lunch', 'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Monday Afternoon', 'dayofweek': '0', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Tuesday Lunch', 'dayofweek': '1', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Tuesday Afternoon', 'dayofweek': '1', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Wednesday Lunch', 'dayofweek': '2', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Wednesday Afternoon', 'dayofweek': '2', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Thursday Lunch', 'dayofweek': '3', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Thursday Afternoon', 'dayofweek': '3', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Friday Morning', 'dayofweek': '4', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Friday Lunch', 'dayofweek': '4', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Friday Afternoon', 'dayofweek': '4', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
            ],
        })

        self.resource_calendar_6_day_week = self.resource_calendar.copy({
            'name': 'Test Calendar 6 Day Week',
            'hours_per_day': 7.6,
            'hours_per_week': 45.6,
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Monday Lunch', 'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Monday Afternoon', 'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Tuesday Lunch', 'dayofweek': '1', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Tuesday Afternoon', 'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Wednesday Lunch', 'dayofweek': '2', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Wednesday Afternoon', 'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Thursday Lunch', 'dayofweek': '3', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Thursday Afternoon', 'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Friday Morning', 'dayofweek': '4', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Friday Lunch', 'dayofweek': '4', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Friday Afternoon', 'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Saturday Morning', 'dayofweek': '5', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Saturday Lunch', 'dayofweek': '5', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Saturday Afternoon', 'dayofweek': '5', 'hour_from': 13, 'hour_to': 16.6, 'day_period': 'afternoon'}),
            ],
        })

        self.resource_calendar_two_weeks = self.resource_calendar.copy({
            'name': 'Test Two Week Calendar No Breaks',
            'hours_per_day': 7.6,
            'hours_per_week': 38,
            'full_time_required_hours': 38,
            'two_weeks_calendar': True,
            'attendance_ids': [
                (0, 0, {'name': 'Monday First Week', 'week_type': '0', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 15.6, 'day_period': 'full_day'}),
                (0, 0, {'name': 'Tuesday First Week', 'week_type': '0', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 15.6, 'day_period': 'full_day'}),
                (0, 0, {'name': 'Wednesday First Week', 'week_type': '0', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 15.6, 'day_period': 'full_day'}),
                (0, 0, {'name': 'Thursday First Week', 'week_type': '0', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 15.6, 'day_period': 'full_day'}),
                (0, 0, {'name': 'Friday First Week', 'week_type': '0', 'dayofweek': '4', 'hour_from': 8, 'hour_to': 15.6, 'day_period': 'full_day'}),
                (0, 0, {'name': 'Monday Second Week', 'week_type': '1', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 15.6, 'day_period': 'full_day'}),
                (0, 0, {'name': 'Tuesday Second Week', 'week_type': '1', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 15.6, 'day_period': 'full_day'}),
                (0, 0, {'name': 'Wednesday Second Week', 'week_type': '1', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 15.6, 'day_period': 'full_day'}),
                (0, 0, {'name': 'Thursday Second Week', 'week_type': '1', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 15.6, 'day_period': 'full_day'}),
                (0, 0, {'name': 'Friday Second Week', 'week_type': '1', 'dayofweek': '4', 'hour_from': 8, 'hour_to': 15.6, 'day_period': 'full_day'}),
            ],
        })

        with freeze_time('2023-01-01'):

            today = date.today()
            self.paid_time_off_type = self.holiday_leave_types  # self.holiday_leave_types.filtered(lambda leave_type: leave_type.validity_start == date(today.year, 1, 1) and leave_type.validity_stop == date(today.year, 12, 31))

            self.employee_gustavo = self.create_employee({
                'name': 'Gustavo Garcia',
                'date_version': date(today.year - 2, 1, 1),
                'contract_date_start': date(today.year - 2, 1, 1),
                'resource_calendar_id': self.resource_calendar_40_hours.id,
            })

            self.employee_fernando = self.create_employee({
                'name': 'Fernando Alonso',
                'date_version': date(today.year - 2, 1, 1),
                'contract_date_start': date(today.year - 2, 1, 1),
                'resource_calendar_id': self.resource_calendar_6_day_week.id,
            })

            self.employee_bertrand = self.create_employee({
                'name': 'Bertrand Guru',
                'date_version': date(today.year - 2, 1, 1),
                'contract_date_start': date(today.year - 2, 1, 1),
                'resource_calendar_id': self.resource_calendar_two_weeks.id,
            })

            self.wizard = self.env['hr.payroll.alloc.paid.leave'].create({
                'year': today.year - 1,
                'holiday_status_id': self.paid_time_off_type.id
            })
            self.wizard.alloc_employee_ids = self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id in [self.employee_georges.id, self.employee_john.id, self.employee_with_attestation.id, self.employee_gustavo.id, self.employee_fernando.id, self.employee_bertrand.id])

    def test_allocating_paid_time_off(self):
        """
        Last year, the employee Georges had these contracts:
        - From 01/01 to 31/05, he worked at mid time, 3 days/week
        - From 01/06 to 31/08, he worked at full time, 5 days/week
        - From 01/09 to 31/12, he worked at 4/5, 4 days/week

        and the employee John Doe had these contracts :
        - From 01/01 to 31/03, he worked at full time
        - From 01/04 to 30/06, he worked at 9/10 time
        - From 01/07 to 30/09, he worked at 4/5 time
        - From 01/10 to 31/12, he worked at mid time

        Normally, we must allocate max 15 days to Georges and 16 days to John for this year.

        Description of the calculations:
        ------------------------------
        - Georges :
            - From 01/01 to 31/05, he worked at mid time, 3 days/week. We compute this: 152 * 1 / 2 * 5 / 12 = 31.6667 hours
            - From 01/06 to 31/08, he worked at full time, 5 days/week. We compute this: 152 * 3 / 12 = 38 hours
            - From 01/09 to 31/12, he worked at 4/5, 4 days/weeks. We compute this: 152 * 4 / 5 * 4 / 12 = 40.53333 hours
            In total, we have 110,200033333 hours and we convert it in days to have the value in paid_time_off
            which is equal to: 14,500004386 days (we round to 15 days) = 110,200033333 / (38 / 5) = 110,200033333 hours / 7.6 hours/day

        - John Doe :
            - From 01/01 To 03/31, we compute: 152 x 3 / 12 = 38 hours
            - From 04/01 To 06/30, we compute: 152 x 9 / 10 x 3 / 12 = 34.2 hours
            - From 07/01 To 09/30, we compute: 152 x 4 / 5 x 3 / 12 = 30.4 hours
            - From 10/01 To 12/31, we compute: 152 x 1 / 2 x 3 / 12 = 19 hours
            In total, we have 121.6 hours and we convert it in days to have the value in paid_time_off which is
            16 days = 121.6 / (38 / 5) = 121.6 hours / 7.6 hours/day
        """
        self.assertEqual(len(self.wizard.alloc_employee_ids), 6, "Normally we should find 6 employees to allocate their paid time off for the next period")

        self.assertEqual(self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_georges.id).paid_time_off, 15, "Georges should have 15 days paid time offs for this year.")
        self.assertEqual(self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_john.id).paid_time_off, 16, "John Doe should have 16 days paid time offs for this year.")
        self.assertEqual(self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_gustavo.id).paid_time_off, 20, "Gustavo should have 20 days paid time offs for this year.")
        self.assertEqual(self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_fernando.id).paid_time_off, 24, "Fernando should have 24 days paid time offs for this year.")
        self.assertEqual(self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_bertrand.id).paid_time_off, 20, "Bertrand should have 20 days paid time offs for this year.")

    def test_reallocate_paid_time_off_based_contract_next_year(self):
        """
        In two first leave we see the paid time off allocated for both employee based on their contract in the last year.
        But we need to check the contract for this year to allocate the correct amount of paid time off.

        This year, Georges begins to work a 4/5 and John continues his last contract at mid-time.

        Description of the calculations:
        ------------------------------
        After the calculation done in test above, we need to convert 110,200033333 in days for the mid time of John, that is :
        110,200033333 / (30.4 hours per week / 4 days) = 14.5 days (we round to 15 days)

        After the calculation done in test above, we need to convert 121.6 in days for the mid time of John, that is :
        121.6 / (19 hours per week / 3 days) = 19.2 days (we round to 19 days)
        But since an employee should never have more than 4 weeks of paid time off, his total is reduced to 4 weeks of 3 days a week aka 12 days
        """
        self.assertEqual(len(self.wizard.alloc_employee_ids), 6, "Normally, we should find 6 employees to allocate their paid time off for the next period")

        alloc_employee = self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_georges.id)
        self.assertEqual(alloc_employee.paid_time_off_to_allocate, 14.5, "With a 4/5 time in this period, Georges could have 16 days of paid time off but his working schedule in last period allow him 14.5 days")

        alloc_employee = self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_john.id)
        self.assertEqual(alloc_employee.paid_time_off_to_allocate, 10, "With a mid-time in this period, John Doe should have 10 half days of paid time off but we must retain that he could have 16 days at total this period")

        view = self.wizard.generate_allocation()
        allocations = self.env['hr.leave.allocation'].search(view['domain'])
        georges_allocation = allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_georges.id)

        self.assertEqual(georges_allocation.number_of_days, 14.5)
        self.assertAlmostEqual(georges_allocation.max_leaves_allocated, 15 * 7.6, places=0, msg="based on the last year, we retain that Georges can have at most 16 days of paid time off")

        john_allocation = allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_john.id)

        self.assertEqual(john_allocation.number_of_days, 10)
        self.assertAlmostEqual(john_allocation.max_leaves_allocated, 16 * 7.6, places=0)

    def test_allocating_paid_time_off_with_attestation_days(self):
        """
        Last year, the Employee With Attestation had these contracts:
        - He worked 3 months for the previous employer with 50% occupation rate.
        - From 01/10 to 31/12, he worked at full time, 5 days/week

        Normally, we must allocate max 8 days to the employee for this year

        Description of the calculations:
        ------------------------------
        - Employee With Attestation :
            - He worked 3 months for the previous employer with 50% occupation rate.
              We compute this: 152 * (3/12) * (50/100) = 19 hours
            - From 01/10 to 31/12, he worked at full time, 5 days/week. We compute this: 152 * 3 / 12 = 38 hours

            In total, we have 57 hours and we convert it in days to have the value in paid_time_off
            which is equal to: 7.5 (Will be rounde to 8) days (57 hours / 7.6 hours/day)
        """
        self.assertEqual(
            self.wizard.alloc_employee_ids.filtered(
                lambda alloc: alloc.employee_id == self.employee_with_attestation
            ).paid_time_off,
            8,
            "The employee should have 8 days paid time offs for this year.")

    # This situation occurred during the migration to the version model. Some employees had one version in BE
    # while the rest of their versions were in HK. Normally, this should not happen because we create a separate
    # employee record for each company, and an employee's versions are linked to the company of that employee.
    def test_allocating_paid_time_off_with_versions_in_different_companies(self):
        """
        Last year, the employee Georges had these contracts: :
        - From 01/01 to 31/05, he worked at mid time, 3 days/week   ->   BE Company
        - From 01/06 to 31/08, he worked at full time, 5 days/week  ->   BE Company
        - From 01/09 to 31/12, he worked at 4/5, 4 days/week        ->   HK Company

        Since Georges switched to HK company on 01/09, there shouldn't be any allocation for him.
        """
        with freeze_time('2023-12-01'):
            hongkong_company = self.env['res.company'].create({
                'name': 'My HK Company - Test',
                'country_id': self.env.ref('base.hk').id,
                'currency_id': self.env.ref('base.EUR').id,
                'street': 'not Rue du Paradis',
                'zip': '6870',
                'city': 'not Eghezee',
                'vat': 'BE0897223670',
                'phone': '061928374',
            })
            self.employee_georges.company_id = hongkong_company.id
            self.employee_georges.flush_recordset()
            last_year = date.today().year - 1
            target_dates = [
                date(last_year, 1, 1),
                date(last_year, 6, 1),
            ]
            versions = self.employee_georges.version_ids.search([
                ('date_version', 'in', target_dates)
            ])
            versions.write({'company_id': self.belgian_company.id})
            self.wizard = self.env['hr.payroll.alloc.paid.leave'].create({
                'year': date.today().year - 1,
                'holiday_status_id': self.paid_time_off_type.id
            })
            self.wizard.alloc_employee_ids = self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_georges.id)
            self.assertEqual(len(self.wizard.alloc_employee_ids), 0, "Since Georges switched to HK company on 01/09, there shouldn't be any allocation for him.")
