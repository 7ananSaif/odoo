# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase
from odoo.fields import Date

from freezegun import freeze_time

PAY_SCHEDULES = {
    'monthly': 30,
    'quarterly': 89,
    'semi-annually': 180,
    'annually': 364,
    'weekly': 6,
    'bi-weekly': 13,
    'bi-monthly': 58,
    'daily': 0,
}

class TestScheduleRelativePayslip(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test - Seaman',
        })
        cls.structure = cls.env['hr.payroll.structure'].create([{
            'name': 'Seaman Monthly Pay',
            'type_id': cls.structure_type.id,
            'schedule_pay': 'monthly',
        }])
        cls.structure_type.default_struct_id = cls.structure

        cls.billy_emp = cls.env['hr.employee'].create({
            'name': 'Billy Bones',
            'sex': 'male',
            'birthday': '1982-03-29',
            'date_version': Date.to_date('2023-01-01'),
            'contract_date_start': Date.to_date('2023-01-01'),
            'contract_date_end': Date.to_date('2023-12-31'),
            'wage': 5000.33,
            'structure_type_id': cls.structure_type.id,
        })
        cls.billy_contract = cls.billy_emp.version_id

    def test_payslip_computes(self):
        with freeze_time('2023-03-12'):
            payslip = self.env['hr.payslip'].new({
                'name': 'Black Spot',
                'employee_id': self.billy_emp.id,
            })
            self.assertEqual(payslip.version_id, self.billy_contract)
            self.assertEqual(payslip.struct_id, self.structure)
            self.assertEqual(payslip.date_from, Date.to_date('2023-03-01'))
            self.assertEqual(payslip.date_to, Date.to_date('2023-03-31'))
            payslip.write({
                'date_from': Date.to_date('2023-01-01'),
            })
            self.assertEqual(payslip.date_to, Date.to_date('2023-01-31'))

    def test_payslip_adapting_to_schedule(self):
        with freeze_time('2023-01-12'):
            # Test default monthly payslip
            payslip_monthly = self.env['hr.payslip'].new({
                'name': 'Black Spot',
                'employee_id': self.billy_emp.id,
            })
            self.assertEqual(payslip_monthly.date_from, Date.to_date('2023-01-01'), "date_from for the monthly payslip should be the first of the current month (2023-01-01)")
            monthly_delta = (payslip_monthly.date_to - payslip_monthly.date_from).days
            self.assertEqual(monthly_delta, PAY_SCHEDULES['monthly'], f"Delta for monthly payslip should be {PAY_SCHEDULES['monthly']} days")

            # Test other pay schedules
            for pay_schedule, expected_delta in PAY_SCHEDULES.items():
                self.billy_contract.write({
                    'schedule_pay': pay_schedule,
                })
                payslip = self.env['hr.payslip'].new({
                    'name': 'Black Spot',
                    'employee_id': self.billy_emp.id,
                })
                self.assertEqual(payslip.date_from, Date.to_date('2023-01-01'), f"date_from for {pay_schedule} payslip should be the first of the current month (2023-04-01)")
                self.assertEqual((payslip.date_to - payslip.date_from).days, expected_delta, f"Delta for {pay_schedule} payslip should be {expected_delta} days")

    def test_payslip_warnings(self):
        with freeze_time('2023-04-12'):
            self.billy_contract.write({
                'schedule_pay': 'quarterly',
            })
            payslip = self.env['hr.payslip'].new({
                'name': 'Black Spot February',
                'employee_id': self.billy_emp.id,
            })

            payslip.date_from = Date.to_date('2022-01-31')
            self.assertTrue(
                payslip.issues and "No running contract over payslip period" in [issue['message'] for issue in payslip.issues.values()],
                "An error should be set on contract validity.")

            payslip.date_to = Date.to_date('2022-05-14')
            self.assertTrue(
                payslip.issues and "No running contract over payslip period" in [issue['message'] for issue in payslip.issues.values()],
                "An error should be set on contract validity.")
            self.assertTrue(
                payslip.issues and "The duration of the payslip is not accurate according to the structure type." in [issue['message'] for issue in payslip.issues.values()],
                "A warning should be set on structure type duration.")
