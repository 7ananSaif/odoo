# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY

from odoo.tests import tagged
from odoo.fields import Command

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestAverageDailyWage(TestL10NHkHrPayrollAccountCommon):
    """
    These tests are based on numbers generated using the official Labour Department calculator.
    """
    def test_average_daily_wage(self):
        """ Validate calculation of basic average daily wage. """
        date_start = date(2025, 1, 1)
        self.contract.write({
            'date_version': date_start,
            'contract_date_start': date_start,
        })

        # Generate slips from january to november.
        for dt in rrule(MONTHLY, dtstart=date_start, until=date_start + relativedelta(month=11)):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        payslip = self._generate_payslip(
            date(2025, 12, 1), date(2025, 12, 31),
            struct_id=self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        )
        self.assertEqual(payslip.l10n_hk_average_daily_wage, 665.27)

    def test_average_daily_wage_unpaid(self):
        """ Validate calculation of basic average daily wage with unpaid leaves. """
        date_start = date(2025, 1, 1)
        self.contract.write({
            'date_version': date_start,
            'contract_date_start': date_start,
        })

        # Generate slips from january to november.
        self._generate_leave(date(2025, 11, 1), date(2025, 11, 5), self.env.ref('hr_holidays.l10n_hk_leave_type_unpaid_leave'))
        for dt in rrule(MONTHLY, dtstart=date_start, until=date_start + relativedelta(month=11)):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        # December
        payslip = self._generate_payslip(
            date(2025, 12, 1), date(2025, 12, 31),
            struct_id=self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        )
        self.assertEqual(payslip.l10n_hk_average_daily_wage, 665.15)

    def test_average_daily_wage_paid_leave(self):
        """ Validate calculation of basic average daily wage with paid leaves. """
        date_start = date(2025, 1, 1)
        self.contract.write({
            'date_version': date_start,
            'contract_date_start': date_start,
        })

        hk_annual_leave_allocation = self.env['hr.leave.allocation'].create({
            'name': 'HK Annual Leave Allocation',
            'holiday_status_id': self.env.ref('hr_holidays.l10n_hk_leave_type_annual_leave').id,
            'number_of_days': 10,
            'employee_id': self.employee.id,
            'state': 'confirm',
            'date_from': '2025-01-01',
        })
        hk_annual_leave_allocation.action_approve()
        self._generate_leave(date(2025, 10, 1), date(2025, 10, 5), self.env.ref('hr_holidays.l10n_hk_leave_type_annual_leave'))
        # Generate slips from january to november.
        for dt in rrule(MONTHLY, dtstart=date_start, until=date_start + relativedelta(month=11)):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        # December
        payslip = self._generate_payslip(
            date(2025, 12, 1), date(2025, 12, 31),
            struct_id=self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        )
        self.assertEqual(payslip.l10n_hk_average_daily_wage, 665.46)

    def test_average_daily_wage_non_full_pay(self):
        """ Validate calculation of basic average daily wage with 80% paid leaves. """
        date_start = date(2025, 1, 1)
        self.contract.write({
            'date_version': date_start,
            'contract_date_start': date_start,
        })

        self._generate_leave(date(2025, 10, 1), date(2025, 10, 5), self.env.ref('hr_holidays.l10n_hk_leave_type_sick_leave_80'))
        # Generate slips from january to november.
        for dt in rrule(MONTHLY, dtstart=date_start, until=date_start + relativedelta(month=11)):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        # December
        payslip = self._generate_payslip(
            date(2025, 12, 1), date(2025, 12, 31),
            struct_id=self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        )
        self.assertEqual(payslip.l10n_hk_average_daily_wage, 665.58)

    def test_manual_average_daily_wage(self):
        """ Validate that setting the input line to manually overwrite the amount works as expected. """
        date_start = date(2025, 1, 1)
        self.contract.write({
            'date_version': date_start,
            'contract_date_start': date_start,
        })

        # Generate slips from january to november.
        for dt in rrule(MONTHLY, dtstart=date_start, until=date_start + relativedelta(month=11)):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        payslip = self._generate_payslip(
            date(2025, 12, 1), date(2025, 12, 31),
            struct_id=self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        )
        self.assertEqual(payslip.l10n_hk_average_daily_wage, 665.27)
        payslip.input_line_ids = [Command.create({
            'input_type_id': self.env.ref('l10n_hk_hr_payroll.input_custom_moving_daily_wage').id,
            'amount': '700',
        })]
        self.assertEqual(payslip.l10n_hk_average_daily_wage, 700)
