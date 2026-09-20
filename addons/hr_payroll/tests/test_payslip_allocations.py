# Part of Odoo. See LICENSE file for full copyright and licensing details.
import random
from datetime import date

from odoo.fields import Command
from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('payslip_allocation')
class TestPayslipAllocations(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Add two bank accounts for Richard
        cls.bank1 = cls.env['res.partner.bank'].create({
            'acc_number': '111-222',
            'partner_id': cls.richard_emp.work_contact_id.id,
        })
        cls.bank2 = cls.env['res.partner.bank'].create({
            'acc_number': '333-444',
            'partner_id': cls.richard_emp.work_contact_id.id,
        })
        cls.richard_emp.bank_account_ids = [
            Command.set([cls.bank1.id, cls.bank2.id])
        ]

        # Default salary distribution: 100% to bank1
        cls.richard_emp.salary_distribution = {
            str(cls.bank1.id): {
                'sequence': 1,
                'amount': 100.0,
                'amount_is_percentage': True,
            },
        }

        cls.richard_payslip = cls.env['hr.payslip'].create({
            'name': 'Payslip of Richard Allocations',
            'employee_id': cls.richard_emp.id,
            'version_id': cls.contract_cdi.id,
            'struct_id': cls.developer_pay_structure.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31),
        })

    def _compute_alloc(self, total=None):
        return self.richard_payslip.compute_salary_allocations(total_amount=total)

    def test_split_hundred_zero_percentages(self):
        """ If percentages split are 100% and 0%, both should appear in allocations """
        self.richard_payslip.net_wage = 1000
        allocations = self._compute_alloc()
        self.assertEqual(len(allocations), 2)
        self.assertIn(str(self.bank1.id), allocations)
        self.assertIn(str(self.bank2.id), allocations)
        self.assertAlmostEqual(
            allocations[str(self.bank1.id)],
            round(self.richard_payslip.net_wage, 2),
            places=2,
        )
        self.assertAlmostEqual(
            allocations[str(self.bank2.id)],
            0
        )

    def test_split_fixed_and_percentage(self):
        """ Fixed allocation goes first, remainder is distributed by percentage """
        self.richard_emp.salary_distribution = {
            str(self.bank1.id): {
                'sequence': 1,
                'amount': 1000.0,
                'amount_is_percentage': False,
            },
            str(self.bank2.id): {
                'sequence': 2,
                'amount': 100.0,
                'amount_is_percentage': True,
            },
        }
        allocations = self._compute_alloc(total=5000.0)
        self.assertAlmostEqual(allocations[str(self.bank1.id)], 1000.0)
        self.assertAlmostEqual(allocations[str(self.bank2.id)], 4000.0)

    def test_percentage_split(self):
        """ Two percentages should split the wage proportionally """
        self.richard_emp.salary_distribution = {
            str(self.bank1.id): {
                'sequence': 1,
                'amount': 60.0,
                'amount_is_percentage': True,
            },
            str(self.bank2.id): {
                'sequence': 2,
                'amount': 40.0,
                'amount_is_percentage': True,
            },
        }
        allocations = self._compute_alloc(total=1000.0)
        self.assertAlmostEqual(allocations[str(self.bank1.id)], 600.0)
        self.assertAlmostEqual(allocations[str(self.bank2.id)], 400.0)

    def test_too_much_fixed_raises(self):
        """ If fixed allocations exceed net wage, ValidationError is raised """
        self.richard_emp.salary_distribution = {
            str(self.bank1.id): {
                'sequence': 1,
                'amount': 6000.0,  # > wage
                'amount_is_percentage': False,
            },
        }
        with self.assertRaisesRegex(Exception, "surpass the net salary"):
            self._compute_alloc(total=5000.0)

    def test_not_fully_allocated_raises(self):
        self.richard_emp.salary_distribution = {
            str(self.bank1.id): {
                'sequence': 1,
                'amount': 2000.0,
                'amount_is_percentage': False,
            },
            str(self.bank2.id): {
                'sequence': 1,
                'amount': 2000.0,
                'amount_is_percentage': False,
            },
        }
        with self.assertRaisesRegex(Exception, "less than the net salary"):
            self._compute_alloc(total=5000.0)

    def test_three_accounts_fixed_and_percentages(self):
        """ One fixed + two percentage allocations """
        self.richard_emp.bank_account_ids = [Command.set([self.bank1.id, self.bank2.id])]

        bank3 = self.env['res.partner.bank'].create({
            'acc_number': '555-666',
            'partner_id': self.richard_emp.work_contact_id.id,
        })
        self.richard_emp.bank_account_ids = [Command.set([self.bank1.id, self.bank2.id, bank3.id])]

        self.richard_emp.salary_distribution = {
            str(self.bank1.id): {
                'sequence': 1,
                'amount': 2000.0,   # fixed
                'amount_is_percentage': False,
            },
            str(self.bank2.id): {
                'sequence': 2,
                'amount': 30.0,     # percentage
                'amount_is_percentage': True,
            },
            str(bank3.id): {
                'sequence': 3,
                'amount': 70.0,     # percentage
                'amount_is_percentage': True,
            },
        }

        allocations = self._compute_alloc(total=10000.0)
        # bank1 gets 2000 fixed
        self.assertAlmostEqual(allocations[str(self.bank1.id)], 2000.0)

        # 8000 left → 30% = 2400, 70% = 5600
        self.assertAlmostEqual(allocations[str(self.bank2.id)], 2400.0)
        self.assertAlmostEqual(allocations[str(bank3.id)], 5600.0)

    def test_three_accounts_multiple_fixed_and_percentage(self):
        """ Two fixed amounts and one percentage allocation """
        bank3 = self.env['res.partner.bank'].create({
            'acc_number': '777-888',
            'partner_id': self.richard_emp.work_contact_id.id,
        })
        self.richard_emp.bank_account_ids = [Command.set([self.bank1.id, self.bank2.id, bank3.id])]

        self.richard_emp.salary_distribution = {
            str(self.bank1.id): {
                'sequence': 1,
                'amount': 1000.0,   # fixed
                'amount_is_percentage': False,
            },
            str(self.bank2.id): {
                'sequence': 2,
                'amount': 2500.0,   # fixed
                'amount_is_percentage': False,
            },
            str(bank3.id): {
                'sequence': 3,
                'amount': 100.0,    # percentage
                'amount_is_percentage': True,
            },
        }

        allocations = self._compute_alloc(total=7000.0)
        self.assertAlmostEqual(allocations[str(self.bank1.id)], 1000.0)
        self.assertAlmostEqual(allocations[str(self.bank2.id)], 2500.0)
        self.assertAlmostEqual(allocations[str(bank3.id)], 3500.0)

    def test_four_accounts_mixed_distribution(self):
        """ Combination of multiple fixed and percentage across 4 accounts """
        bank3 = self.env['res.partner.bank'].create({
            'acc_number': '999-000',
            'partner_id': self.richard_emp.work_contact_id.id,
        })
        bank4 = self.env['res.partner.bank'].create({
            'acc_number': '121-212',
            'partner_id': self.richard_emp.work_contact_id.id,
        })
        self.richard_emp.bank_account_ids = [Command.set([self.bank1.id, self.bank2.id, bank3.id, bank4.id])]

        self.richard_emp.salary_distribution = {
            str(self.bank1.id): {
                'sequence': 1,
                'amount': 500.0,    # fixed
                'amount_is_percentage': False,
            },
            str(self.bank2.id): {
                'sequence': 2,
                'amount': 20.0,     # %
                'amount_is_percentage': True,
            },
            str(bank3.id): {
                'sequence': 3,
                'amount': 30.0,     # %
                'amount_is_percentage': True,
            },
            str(bank4.id): {
                'sequence': 4,
                'amount': 50.0,     # %
                'amount_is_percentage': True,
            },
        }

        allocations = self._compute_alloc(total=10000.0)
        # fixed first
        self.assertAlmostEqual(allocations[str(self.bank1.id)], 500.0)
        # 9500 left → split 20/30/50
        self.assertAlmostEqual(allocations[str(self.bank2.id)], 1900.0)
        self.assertAlmostEqual(allocations[str(bank3.id)], 2850.0)
        self.assertAlmostEqual(allocations[str(bank4.id)], 4750.0)

    def test_rounding_residual_is_absorbed(self):
        """Rounding differences must be absorbed so that the sum equals the net wage"""
        bank3 = self.env['res.partner.bank'].create({
            'acc_number': '131-313',
            'partner_id': self.richard_emp.work_contact_id.id,
        })
        self.richard_emp.write({
            "bank_account_ids": [Command.set([self.bank1.id, self.bank2.id, bank3.id])]
        })

        # Fixed 3-way split: 33.33%, 33.33%, 33.34%
        self.richard_emp.salary_distribution = {
            str(self.bank1.id): {
                'sequence': 1,
                'amount': 33.33,
                'amount_is_percentage': True,
            },
            str(self.bank2.id): {
                'sequence': 2,
                'amount': 33.33,
                'amount_is_percentage': True,
            },
            str(bank3.id): {
                'sequence': 3,
                'amount': 33.34,
                'amount_is_percentage': True,
            },
        }

        random.seed(42)
        totals = [round(random.uniform(100, 5000), 2) for _ in range(50)]

        for total in totals:
            allocations = self._compute_alloc(total=total)
            summed = sum(allocations.values())

            # Sum must equal net wage to 2 decimals
            self.assertAlmostEqual(summed, total, places=2)
