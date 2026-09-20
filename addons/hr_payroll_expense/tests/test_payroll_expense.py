# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.exceptions import UserError
from odoo.addons.hr_expense.tests.common import TestExpenseCommon
from odoo.addons.hr_payroll_account.tests.test_hr_payroll_account import TestHrPayrollAccountCommon


@tagged('post_install', '-at_install')
class TestPayrollExpense(TestHrPayrollAccountCommon, TestExpenseCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company_data['company'].id]))
        cls.company.tax_calculation_rounding_method = 'round_per_line'

        cls.payslip_run.company_id = cls.company_data['company'].id

        # Else the payslip_run will be using the the demo company in its environment, thus raising an error
        # when payslip_run.action_validate() is called. Because the demo company doesn't have a journal
        # and payslip_run.slip_ids.journal_id is company dependent
        cls.payslip_run.env = cls.env

        cls.expense_employee.update({
            'sex': 'male',
            'birthday': '1984-05-01',
            'company_id': cls.company_data['company'].id,
            'country_id': cls.company_data['company'].country_id.id,
            'department_id': cls.dep_rd.id,
            'date_version': cls.frozen_today - relativedelta(years=2),
            'contract_date_start': cls.frozen_today - relativedelta(years=2),
            'contract_date_end': cls.frozen_today + relativedelta(years=2),
            'wage': 5000.33,
            'structure_type_id': cls.hr_structure_type.id,
        })
        cls.expense_contract = cls.expense_employee.version_id
        work_entry_vals = cls.env['hr.version']._generate_work_entries_postprocess([{
            'name': 'Work Entry',
            'employee_id': cls.expense_employee.id,
            'date_start': cls.frozen_today - relativedelta(days=1),
            'date_stop': cls.frozen_today,
            'version_id': cls.expense_contract.id,
            'state': 'validated',
        }])
        cls.expense_work_entry = cls.env['hr.work.entry'].create(work_entry_vals)
        cls.expense_payslip_input = cls.env.ref('hr_payroll_expense.expense_other_input')
        expense_payslip_tax_account = cls.env['account.account'].create({
                'name': 'Rental Tax',
                'code': '777777',
                'account_type': 'asset_current',
            })
        expense_tax = cls.env['account.tax'].create({
            'name': "Some taxes on normal payslip",
            'amount_type': 'percent',
            'amount': 10.0,
            'type_tax_use': 'sale',
            'company_id': cls.company_data['company'].id,
            'invoice_repartition_line_ids': [
                Command.create({'factor_percent': 100, 'repartition_type': 'base'}),
                Command.create({'factor_percent': 100, 'account_id': expense_payslip_tax_account.id}),
            ],
            'refund_repartition_line_ids': [
                Command.create({'factor_percent': 100, 'repartition_type': 'base'}),
                Command.create({'factor_percent': 100, 'account_id': expense_payslip_tax_account.id}),
            ],
        })
        test_account = cls.env['account.account'].create({
                'name': 'House Rental',
                'code': '654321',
                'account_type': 'income',
                'tax_ids': [Command.link(expense_tax.id)],
        })
        cls.expense_payable_account = cls.env['account.account'].create({
                'name': 'payable',
                'code': '654323',
                'account_type': 'liability_payable',
            })
        cls.expense_payslip_journal = cls.env['account.journal'].create({
            'name': 'EXPENSE',
            'code': 'EXP',
            'type': 'general',
            'company_id': cls.company_data['company'].id,
        })
        cls.expense_hr_structure = cls.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for Software Developer',
            'journal_id': cls.expense_payslip_journal.id,
            'rule_ids': [Command.create({
                'name': 'Basic Salary',
                'amount_select': 'code',
                'amount_python_compute': 'result = version.wage',
                'code': 'BASIC',
                'category_id': cls.env.ref('hr_payroll.BASIC').id,
                'sequence': 1,
                'account_debit': test_account.id,
            }), Command.create({
                'name': 'House Rent Allowance',
                'amount_select': 'percentage',
                'amount_percentage': 40,
                'amount_percentage_base': 'version.wage',
                'code': 'HRA',
                'category_id': cls.env.ref('hr_payroll.ALW').id,
                'sequence': 5,
                'account_debit': test_account.id,
            }), Command.create({
                'name': 'Reimbursed Expenses',
                'amount_select': 'input',
                'condition_other_input_id': cls.expense_payslip_input.id,
                'amount_other_input_id': cls.expense_payslip_input.id,
                'code': 'EXPENSES',
                'category_id': cls.env.ref('hr_payroll.ALW').id,
                'sequence': 6,
                'account_debit': cls.expense_payable_account.id,
            }), Command.create({
                'name': 'Net Salary',
                'amount_select': 'code',
                'amount_python_compute': 'result = categories["BASIC"] + categories["ALW"] + categories["DED"]',
                'code': 'NET',
                'category_id': cls.env.ref('hr_payroll.NET').id,
                'sequence': 10,
                'account_credit': test_account.id,
            })],
            'type_id': cls.env['hr.payroll.structure.type'].create({'name': 'Employee', 'country_id': False}).id,
        })
        cls.expense_salary_rule = cls.expense_hr_structure.rule_ids.filtered(lambda rule: rule.code == 'EXPENSES')

    def create_payslip(self, vals=None):
        return self.env['hr.payslip'].create({
            'name': 'Payslip',
            'employee_id': self.expense_employee.id,
            'struct_id': self.expense_hr_structure.id,
            'version_id': self.expense_contract.id,
            'payslip_run_id': self.payslip_run.id,
            'date_from': self.frozen_today - relativedelta(months=1),
            'date_to': self.frozen_today,
            'company_id': self.company_data['company'].id,
            **(vals or {})
        })

    def get_reconciliation_lines_from_accounts(self, account_ids):
        """ Helper function to return reconciled lines linked to specific accounts """
        return self.env['account.partial.reconcile'].search([
            '|', ('debit_move_id.account_id', 'in', account_ids), ('credit_move_id.account_id', 'in', account_ids),
        ])

    @staticmethod
    def get_all_amls_to_be_reconciled(expenses, payslips, include_payslips_payment_terms_amls=False):
        """  Helper function to return all the amls required to test the reconciliation """

        expenses_amls = expenses.account_move_id.line_ids.filtered(lambda line: line.display_type == 'payment_term')

        payslip_payable_lines = payslips.move_id.line_ids.filtered(lambda line: line.account_type == 'liability_payable')
        if include_payslips_payment_terms_amls:
            return expenses_amls, payslip_payable_lines

        payslip_payment_terms = payslip_payable_lines.filtered(lambda line: line.display_type == 'payment_term')
        payslip_expense_lines = payslip_payable_lines - payslip_payment_terms
        return expenses_amls, payslip_expense_lines

    @freeze_time('2022-01-25')
    def test_main_flow_expense_in_payslip(self):
        expense_1 = self.create_expenses({'name': 'Expense'})
        expense_2 = self.create_expenses({
            'name': 'Expense 2',
            'total_amount_currency': 3000,
        })
        expenses = expense_1 | expense_2
        expenses_total_amount = sum(expenses.mapped('total_amount'))
        expenses.action_submit()
        expenses.action_approve()
        for expense in expenses:  # Ensure each expense as a unique move
            self.post_expenses_with_wizard(expense)
        expenses.action_report_in_next_payslip()

        # Creating payslip links the expense to the payslip
        payslip = self.create_payslip()
        self.assertRecordValues(expenses, [
            {'payslip_id': payslip.id, 'state': 'posted', 'account_move_id': expense_1.account_move_id.id},
            {'payslip_id': payslip.id, 'state': 'posted', 'account_move_id': expense_2.account_move_id.id},
        ])
        self.assertRecordValues(payslip, [
            {'expense_ids': expenses.ids, 'state': 'draft', 'employee_id': self.expense_employee.id},
        ])
        self.assertRecordValues(payslip.input_line_ids, [
            {'input_type_id': self.expense_payslip_input.id, 'amount': expenses_total_amount},
        ])

        # Test removing expense from payslip unlinks the two
        expense_1.action_remove_from_payslip()
        self.assertRecordValues(expenses, [
            {'name': 'Expense',   'state': 'posted', 'payslip_id': False,      'account_move_id': expense_1.account_move_id.id},
            {'name': 'Expense 2', 'state': 'posted', 'payslip_id': payslip.id, 'account_move_id': expense_2.account_move_id.id},
        ])
        self.assertRecordValues(payslip, [
            {'expense_ids': expense_2.ids, 'state': 'draft', 'employee_id': self.expense_employee.id},
        ])
        self.assertRecordValues(payslip.input_line_ids, [
            {'input_type_id': self.expense_payslip_input.id, 'amount': expense_2.total_amount},
        ])

        expense_2.action_remove_from_payslip()
        self.assertRecordValues(expenses, [
            {'state': 'posted', 'payslip_id': False, 'account_move_id': expense_1.account_move_id.id},
            {'state': 'posted', 'payslip_id': False, 'account_move_id': expense_2.account_move_id.id},
        ])
        self.assertRecordValues(payslip, [
            {'expense_ids': [], 'state': 'draft', 'employee_id': self.expense_employee.id},
        ])
        self.assertFalse(payslip.input_line_ids)

        # This should re-add the expense to the payslip
        expenses.action_report_in_next_payslip()
        payslip.action_payslip_draft()
        self.assertRecordValues(expenses, [
            {'state': 'posted', 'payslip_id': payslip.id, 'account_move_id': expense_1.account_move_id.id},
            {'state': 'posted', 'payslip_id': payslip.id, 'account_move_id': expense_2.account_move_id.id},
        ])

        # Moving up to setting the payslip as done shouldn't change anything for the expense
        self.payslip_run.slip_ids.compute_sheet()
        self.payslip_run.action_validate()
        self.assertRecordValues(expenses, [
            {'state': 'posted', 'payslip_id': payslip.id, 'account_move_id': expense_1.account_move_id.id},
            {'state': 'posted', 'payslip_id': payslip.id, 'account_move_id': expense_2.account_move_id.id},
        ])
        # Test trying to remove the expense from the payslip when a payslip has generated a move raises an error
        with self.assertRaises(UserError):
            expense_1.action_remove_from_payslip()
        with self.assertRaises(UserError):
            expense_1.action_reset()

        # Posting the payslip move should post the expense moves
        payslip.move_id.action_post()
        expenses_lines_to_reconcile, payslip_lines_to_reconcile = \
            self.get_all_amls_to_be_reconciled(expenses, payslip, include_payslips_payment_terms_amls=True)

        self.assertRecordValues(expenses_lines_to_reconcile.sorted('balance'), [
            {'balance': -expense_2.total_amount},
            {'balance': -expense_1.total_amount},
        ])
        self.assertRecordValues(payslip_lines_to_reconcile, [
            {'balance': expenses_total_amount, 'account_id': self.expense_payable_account.id},
        ])
        reconciliation_lines = self.get_reconciliation_lines_from_accounts(
            (expenses_lines_to_reconcile | payslip_lines_to_reconcile).account_id.ids
        )
        self.assertTrue(reconciliation_lines, "There should be automatic reconciliation lines as it's the most simple case")

        # Because the expense & the payslip moves don't have the same account, there should be a misc entry generated
        misc_move = reconciliation_lines.debit_move_id.move_id - (expenses.account_move_id | payslip.move_id)
        self.assertEqual(
            len(misc_move),
            1,
            "Because the expense & the payslip moves don't have the same account, there should be a misc entry generated",
        )

        misc_move_lines = misc_move.line_ids.sorted('balance')
        self.assertRecordValues(reconciliation_lines.sorted('amount'), [
            {'amount': expense_1.total_amount, 'debit_move_id': misc_move_lines.ids[1], 'credit_move_id': expenses_lines_to_reconcile.ids[0]},
            {'amount': expense_2.total_amount, 'debit_move_id': misc_move_lines.ids[1], 'credit_move_id': expenses_lines_to_reconcile.ids[1]},
            {'amount': expenses_total_amount, 'debit_move_id': payslip_lines_to_reconcile.id, 'credit_move_id': misc_move_lines.ids[0]},
        ])

        # Test reversing the payslip move keeps the expense linked to the payslip
        payslip.move_id.button_draft()
        payslip.move_id.unlink()
        self.assertRecordValues(expenses, [
            {'state': 'approved', 'payslip_id': payslip.id, 'account_move_id': False},
            {'state': 'approved', 'payslip_id': payslip.id, 'account_move_id': False},
        ])
        payslip.action_payslip_draft()
        payslip.unlink()
        self.assertRecordValues(expenses, [
            {'state': 'approved', 'payslip_id': False, 'account_move_id': False},
            {'state': 'approved', 'payslip_id': False, 'account_move_id': False},
        ])

    @freeze_time('2022-01-25')
    def test_corner_case_expense_with_expense_payslip_same_payable_account(self):
        """
        Test posting the payslip move, in the case where the payable account is the same for both the payslip & the expense moves
        """
        expense = self.create_expenses()
        expense.action_submit()
        expense.action_approve()
        self.post_expenses_with_wizard(expense)
        expense.action_report_in_next_payslip()

        self.assertRecordValues(expense, [
            {'total_amount': 1000.0, 'state': 'posted'},
        ])
        self.assertRecordValues(expense.account_move_id, [
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid', 'state': 'posted'},
        ])

        # Sets the expense rule on the payroll expense rule
        self.expense_salary_rule.account_debit = expense._get_expense_account_destination()

        payslip = self.create_payslip()
        self.assertEqual(
            1000.0,
            payslip.input_line_ids.filtered(lambda rule: rule.code == 'EXPENSES').amount,
            "The expense total amount should be added to the new payslip expense input line",
        )
        payslip.compute_sheet()
        payslip.action_payslip_done()
        payslip.move_id.action_post()

        # Check reconciliation
        # Get the corresponding account.partial.reconcile lines
        expense_line_to_reconcile, payslip_line_to_reconcile = self.get_all_amls_to_be_reconciled(expense, payslip)
        reconciliation_lines = self.get_reconciliation_lines_from_accounts([expense._get_expense_account_destination()])

        misc_move = reconciliation_lines.debit_move_id.move_id - (expense.account_move_id | payslip.move_id)
        self.assertFalse(
            misc_move,
            "Because the expense & the payslip moves have the same account, there should be no misc entry generated",
        )

        self.assertRecordValues(reconciliation_lines.sorted('amount'), [
            {'amount': 1000.0, 'debit_move_id': payslip_line_to_reconcile.id, 'credit_move_id': expense_line_to_reconcile.id},
        ])

    @freeze_time('2022-01-25')
    def test_corner_case_expense_with_all_identical_payable_accounts(self):
        """
        Similar case than `test_corner_case_expense_with_expense_payslip_same_payable_account`
        except that the payslip payment term account is also the same
        """
        expense = self.create_expenses()
        expense.action_submit()
        expense.action_approve()
        self.post_expenses_with_wizard(expense)
        expense.action_report_in_next_payslip()

        self.assertRecordValues(expense, [
            {'total_amount': 1000.0, 'state': 'posted'},
        ])
        self.assertRecordValues(expense.account_move_id, [
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid', 'state': 'posted'},
        ])

        # Sets the expense rule on the payroll expense rule & NET rule
        self.expense_salary_rule.account_debit = expense._get_expense_account_destination()
        net_rule = self.expense_hr_structure.rule_ids.filtered(lambda rule: rule.code == 'NET')
        net_rule.account_credit = expense._get_expense_account_destination()

        payslip = self.create_payslip()
        self.assertEqual(
            1000.0,
            payslip.input_line_ids.filtered(lambda rule: rule.code == 'EXPENSES').amount,
            "The expense total amount should be added to the new payslip expense input line",
        )
        payslip.compute_sheet()
        payslip.action_payslip_done()
        payslip.move_id.action_post()

        # Check reconciliation
        # Get the corresponding account.partial.reconcile lines
        reconciliation_lines = self.get_reconciliation_lines_from_accounts([expense._get_expense_account_destination()])

        misc_move = reconciliation_lines.debit_move_id.move_id - (expense.account_move_id | payslip.move_id)
        self.assertFalse(
            misc_move,
            "Because the expense & the payslip moves have the same account, there should be no misc entry generated",
        )

        expense_line_to_reconcile, payslip_line_to_reconcile = \
            self.get_all_amls_to_be_reconciled(expense, payslip, include_payslips_payment_terms_amls=True)

        payslip_line_reconciled = payslip_line_to_reconcile.filtered('reconciled')
        self.assertEqual(len(payslip_line_reconciled), 1, "Only one line should be reconciled")
        self.assertEqual(
            payslip_line_reconciled.name,
            'Reimbursed Expenses',
            'The expected Expense line should be the one that is reconciled',
        )

        self.assertRecordValues(reconciliation_lines.sorted('amount'), [
            {'amount': 1000.0, 'debit_move_id': payslip_line_reconciled.id, 'credit_move_id': expense_line_to_reconcile.id},
        ])

    @freeze_time('2022-01-25')
    def test_corner_case_expense_edited_expense_move(self):
        """
        Test that, as you can edit the expense account move independently of the expense, it will still prepare the reconciliation if the
        totals do not match (as it would require a write-off misc move & user input to select a write-off account)
        """
        expenses = self.create_expenses([
            {
                'name': 'Expense To Keep',
                'employee_id': self.expense_employee.id,
                'product_id': self.product_c.id,
                'total_amount_currency': 1000.00,
                'tax_ids': [Command.set(self.tax_purchase_a.ids)],
                'date': '2022-01-26',
                'company_id': self.company_data['company'].id,
                'currency_id': self.company_data['currency'].id,
            },
            {
                'name': 'Expense To Edit',
                'employee_id': self.expense_employee.id,
                'product_id': self.product_c.id,
                'total_amount_currency': 2000.00,
                'tax_ids': [Command.set(self.tax_purchase_a.ids)],
                'date': '2022-01-25',
                'company_id': self.company_data['company'].id,
                'currency_id': self.company_data['currency'].id,
            },
        ])
        expenses.action_submit()
        expenses.action_approve()
        self.post_expenses_with_wizard(expenses)
        expenses.action_report_in_next_payslip()

        self.assertRecordValues(expenses, [
            {'total_amount': 1000.0, 'state': 'posted'},
            {'total_amount': 2000.0, 'state': 'posted'},
        ])
        self.assertRecordValues(expenses.account_move_id, [
            {'amount_total': 3000.0, 'amount_residual': 3000.0, 'payment_state': 'not_paid', 'state': 'posted'},
        ])

        # Edit the total_amount on the expense move by duplicating the product line
        line_to_duplicate = expenses.account_move_id.line_ids.filtered(lambda line: 'Expense To Edit' in (line.name or ""))[:1]
        line_to_duplicate.move_id.button_draft()
        line_to_duplicate.copy()
        line_to_duplicate.move_id.action_post()

        self.assertRecordValues(expenses.account_move_id, [
            {'amount_total': 5000.0, 'amount_residual': 5000.0, 'payment_state': 'not_paid', 'state': 'posted'},
        ])

        payslip = self.create_payslip()
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self.assertEqual(
            3000,
            payslip.input_line_ids.filtered(lambda rule: rule.code == 'EXPENSES').amount,
            "The expenses total amount should be added to the new payslip expense input line",
        )
        payslip.move_id.action_post()

        # Check the two moves are NOT reconciled
        # Get the corresponding account.partial.reconcile lines
        expense_lines_to_reconcile, payslip_line_to_reconcile = self.get_all_amls_to_be_reconciled(expenses, payslip)
        reconciliation_lines = self.get_reconciliation_lines_from_accounts(
            (expense_lines_to_reconcile | payslip_line_to_reconcile).account_id.ids
        )
        self.assertFalse(
            reconciliation_lines,
            "Because the expense & the payslip moves don't have the same amount, there should be no reconciliation",
        )
        self.assertRecordValues(expenses, [
            {'state': 'posted'},
            {'state': 'posted'},
        ])
        self.assertRecordValues(expenses.account_move_id, [
            {'payment_state': 'not_paid', 'amount_residual': 5000.00},
        ])

        self.assertSequenceEqual(
            [f'I0000000000-{payslip.move_id.id}-{min(expenses.account_move_id.ids)}'] * 2,
            [*expense_lines_to_reconcile.mapped('matching_number'), payslip_line_to_reconcile.matching_number],
            "A temporary matching number should still be present on the account move lines to help manually reconcile them"
        )

    def test_already_paid_expense(self):
        """
         Test that you can post the move of your payslip, even if the expense has been flagged to be reimbursed through a payslip,
         but still got paid the "common way"
         """
        paid_or_in_payment_state = self.env['account.move']._get_invoice_in_payment_state()

        expense_paid_before_payslip_creation = self.create_expenses()
        expense_paid_before_payslip_move_posting = self.create_expenses()
        expense_normal = self.create_expenses()
        expenses = expense_paid_before_payslip_creation | expense_paid_before_payslip_move_posting | expense_normal
        expenses.action_submit()
        expenses._do_approve()  # Skip duplicate wizard
        for expense in expenses:  # Ensure we get three distinct moves
            self.post_expenses_with_wizard(expense)
        expenses.action_report_in_next_payslip()

        self.assertRecordValues(expenses, [
            {'total_amount': 1000.0, 'state': 'posted', 'refund_in_payslip': True, 'payslip_id': False},
            {'total_amount': 1000.0, 'state': 'posted', 'refund_in_payslip': True, 'payslip_id': False},
            {'total_amount': 1000.0, 'state': 'posted', 'refund_in_payslip': True, 'payslip_id': False},
        ])
        self.assertRecordValues(expenses.account_move_id, [
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid', 'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid', 'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid', 'state': 'posted'},
        ])

        self.get_new_payment(expense_paid_before_payslip_creation, 1000.0)
        self.assertRecordValues(expenses.sorted('state'), [
            # refund_in_payslip flag isn't reset, but we currently do not need it to be
            {'total_amount': 1000.0, 'state': paid_or_in_payment_state, 'refund_in_payslip': True, 'payslip_id': False},
            {'total_amount': 1000.0, 'state': 'posted',                 'refund_in_payslip': True, 'payslip_id': False},
            {'total_amount': 1000.0, 'state': 'posted',                 'refund_in_payslip': True, 'payslip_id': False},
        ])
        self.assertRecordValues(expenses.account_move_id.sorted('payment_state'), [
            {'amount_total': 1000.0, 'amount_residual': 0.0,    'payment_state': paid_or_in_payment_state, 'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid',               'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid',               'state': 'posted'},
        ])
        payslip = self.create_payslip()
        self.assertEqual(
            2000.0,
            payslip.input_line_ids.filtered(lambda rule: rule.code == 'EXPENSES').amount,
            "The expense total amount of the two expenses in 'approve' state should be added to the new payslip expense input line",
        )
        payslip.compute_sheet()
        payslip.action_payslip_done()

        ctx = {'active_model': 'account.move', 'active_ids': expense_paid_before_payslip_move_posting.account_move_id.ids}
        payment_register = self.env['account.payment.register'].with_context(**ctx).create({
                'amount': expense_paid_before_payslip_move_posting.total_amount,
                'journal_id': self.company_data['default_journal_bank'].id,
                'payment_method_line_id': self.inbound_payment_method_line.id,
            })
        self.assertTrue(
            payment_register.is_already_paid_through_a_payslip,
            "We should have a warning that it's a bad idea to pay twice",
        )
        payment_register._create_payments()

        self.assertEqual(
            2000,
            payslip.input_line_ids.filtered(lambda rule: rule.code == 'EXPENSES').amount,
            "The 2 linked expenses total amounts should be added to the new payslip expense input line",
        )
        self.assertRecordValues(expenses.sorted('state'), [
            {'total_amount': 1000.0, 'state': paid_or_in_payment_state, 'payslip_id': False},
            {'total_amount': 1000.0, 'state': paid_or_in_payment_state, 'payslip_id': payslip.id},
            {'total_amount': 1000.0, 'state': 'posted',                 'payslip_id': payslip.id},
        ])
        self.assertRecordValues(expenses.account_move_id.sorted('state'), [
            {'amount_total': 1000.0, 'amount_residual': 0.0,    'payment_state': paid_or_in_payment_state, 'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 0.0,    'payment_state': paid_or_in_payment_state, 'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid',               'state': 'posted'},
        ])

        # Posting the move will result in `expense_paid_before_payslip_move_posting` being paid twice,
        # but as the warning has been ignored it's the user's problem. It should not raise
        payslip.move_id.action_post()

        # Check reconciliation
        # Get the corresponding account.partial.reconcile lines
        reconciliation_lines = self.get_reconciliation_lines_from_accounts([expense_normal._get_expense_account_destination()])

        misc_moves = reconciliation_lines.debit_move_id.move_id - (expenses.account_move_id | payslip.move_id)
        self.assertEqual(
            2,
            len(misc_moves),
            "There should be two moves, corresponding to the two payments done, as the payslip won't be automatically reconciled",
        )

        # 2 of the three lines of expense_lines_to_reconcile should be reconciled by the early payment, the last one should not
        expense_lines_to_reconcile, payslip_line_to_reconcile = self.get_all_amls_to_be_reconciled(expenses, payslip)

        self.assertFalse(
            payslip_line_to_reconcile.reconciled,
        "The payslip move should not be reconciled as one of the expense being already reconciled, there is a mismatch in the amounts",
        )
        expense_line_not_reconciled = expense_lines_to_reconcile.filtered(
            lambda line: line.matching_number == payslip_line_to_reconcile.matching_number
        )
        self.assertEqual(
            1,
            len(expense_line_not_reconciled),
            "One of the expense should be prepared for manual reconciliation with the payslip move, the one that wasn't paid before posting the payslip move"
        )
        expense_lines_reconciled = (expense_lines_to_reconcile - expense_line_not_reconciled).sorted('id')
        self.assertEqual(
            2,
            len(expense_lines_reconciled),
            "The two other expense lines should be properly reconciled"
        )
        pattern = re.compile(r'^\d+$')
        self.assertRegex(expense_lines_reconciled[0].matching_number, pattern, "The matching number should be a definitive one")
        self.assertRegex(expense_lines_reconciled[1].matching_number, pattern, "The matching number should be a definitive one")
        # Sorting by ID as there are two distinct reconciliation steps
        self.assertRecordValues(reconciliation_lines.sorted('id'), [
            {'amount': 1000.0, 'debit_move_id': misc_moves[0].line_ids.sorted('balance').ids[-1], 'credit_move_id': expense_lines_reconciled[0].id},
            {'amount': 1000.0, 'debit_move_id': misc_moves[1].line_ids.sorted('balance').ids[-1], 'credit_move_id': expense_lines_reconciled[1].id},
        ])

    @freeze_time('2024-01-01')
    def test_no_expense_rule_means_no_linkage(self):
        new_structure_rules = [
            Command.link(rule.copy().id) for rule in self.expense_hr_structure.rule_ids.filtered(lambda rule: rule.code != 'EXPENSES')
        ]
        new_structure_rules.append(Command.create({
            'name': 'Flat rate to ensure at least one move line',
            'amount_select': 'code',
            'amount_python_compute': 'result = 1000',
            'code': 'FLAT',
            'category_id': self.env.ref('hr_payroll.BASIC').id,
            'sequence': 1000,
            'account_debit': self.env['account.account'].create({
                'name': 'random account',
                'code': '652222',
                'account_type': 'expense',
                'tax_ids': [],
                'company_ids': [Command.set(self.company_data['company'].ids)],
            }).id,
        }))
        self.expense_payslip_journal.default_account_id = self.expense_payable_account.id
        structure_without_expense_rule = self.expense_hr_structure.copy({
            'rule_ids': new_structure_rules,
            'journal_id': self.expense_payslip_journal.id,
        })

        expense = self.create_expenses()
        expense.action_submit()
        expense.action_approve()
        self.post_expenses_with_wizard(expense)
        expense.action_report_in_next_payslip()

        payslip = self.create_payslip({
            'struct_id': structure_without_expense_rule.id,
        })

        # No expense linked if there are no expense rule in the structure
        self.assertFalse(payslip.expense_ids)
        self.payslip_run.slip_ids.compute_sheet()
        self.payslip_run.action_validate()
        payslip.move_id.action_post()

        self.assertRecordValues(expense, [
            {'state': 'posted', 'refund_in_payslip': True, 'payslip_id': False},
        ])

    @freeze_time('2024-01-01')
    def test_unlink_payslip_moves_user(self):
        """ Test Account user are able to reset to draft payslip move and unlink them """
        user = self.env['res.users'].create({
            'name': 'Account user',
            'login': 'accountuser',
            'password': 'accountuser',
            'group_ids': [
                Command.link(self.env.ref('account.group_account_user').id),
            ],
        })

        expense = self.create_expenses()
        expense.action_submit()
        expense.action_approve()
        self.post_expenses_with_wizard(expense, date='2023-07-11')
        expense.action_report_in_next_payslip()

        payslip = self.create_payslip()
        self.payslip_run.slip_ids.compute_sheet()
        self.payslip_run.action_validate()
        payslip.move_id.action_post()

        payslip.move_id.with_user(user).button_draft()
        payslip.move_id.with_user(user).unlink()

    @freeze_time('2025-01-01')
    def test_report_in_next_payslip_manager_rights(self):
        with self.with_user(self.expense_user_manager.login):
            expense = self.create_expenses()
            expense.action_submit()
            expense.action_approve()
            self.post_expenses_with_wizard(expense)
            expense.action_report_in_next_payslip()
