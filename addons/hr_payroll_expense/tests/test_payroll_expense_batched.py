# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time

from odoo import Command
from odoo.addons.hr_payroll_expense.tests.test_payroll_expense import TestPayrollExpense
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPayrollExpenseBatched(TestPayrollExpense):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls.company.batch_payroll_move_lines = True
        expenses_vals = []
        payslips_vals = []
        for idx, employee_vals in ((idx, {'name': f'Clone n°{idx:0>2}', 'email': f'clone_{idx}@clone.clone'}) for idx in range(10)):
            new_partner = cls.env['res.partner'].create(employee_vals)
            new_employee = cls.env['hr.employee'].create({
                'name': employee_vals['name'],
                'company_id': cls.company_data['company'].id,
                'country_id': cls.company_data['company'].country_id.id,
                'department_id': cls.dep_rd.id,
                'work_contact_id': new_partner.id,
                'date_version': '2020-01-01',
                'contract_date_start': '2020-01-01',
                'contract_date_end': '2062-01-25',
                'wage': 5000.33,
                'structure_type_id': cls.hr_structure_type.id,
            })
            expenses_vals.append({
                'name': f"Test Expense {employee_vals['name']}",
                'employee_id': new_employee.id,
                'product_id': cls.product_c.id,
                'total_amount_currency': 1000 + idx,
                'tax_ids': [Command.set(cls.tax_purchase_a.ids)],
            })
            payslips_vals.append(
                {
                    'name': f"Payslip for {employee_vals['name']}",
                    'employee_id': new_employee.id,
                    'struct_id': cls.expense_hr_structure.id,
                    'version_id': new_employee.version_id.id,
                    'payslip_run_id': cls.payslip_run.id,
                    'date_from': '2022-01-01',
                    'date_to': '2022-01-25',
                    'company_id': cls.company_data['company'].id
                }
            )

        cls.batched_expenses = cls.env['hr.expense'].create(expenses_vals)
        cls.batched_expenses.action_submit()
        cls.batched_expenses._do_approve()  # Skip duplicate wizard
        cls.post_expenses_with_wizard(cls.batched_expenses, date='2022-01-15')
        cls.batched_expenses.action_report_in_next_payslip()

        cls.batched_payslips = cls.env['hr.payslip'].create(payslips_vals)

    @freeze_time('2022-01-25')
    def test_corner_case_batched_payslips_simple_case(self):
        """ Test that the link is still properly done when payslips are accounted for in batches """
        self.batched_payslips.compute_sheet()
        self.payslip_run.action_validate()

        self.assertSequenceEqual(
            ['posted'] * 10,
            self.batched_expenses.account_move_id.mapped('state'),
        )

        self.payslip_run.slip_ids.move_id.action_post()
        self.assertSequenceEqual(
            ['posted'] * 10,
            self.batched_expenses.account_move_id.mapped('state'),
            "All expense moves should be automatically posted when posting the payslip one",
        )

        self.assertEqual(1, len(self.payslip_run.slip_ids.move_id))
        self.assertSequenceEqual(
            ['paid'] * 10,
            self.batched_expenses.mapped('state'),
            "All expense moves should be paid and reconciled with the payslips move",
        )

        # Check reconciliation
        # Get the corresponding account.partial.reconcile lines
        expenses_lines_to_reconcile, payslips_lines_to_reconcile = \
            self.get_all_amls_to_be_reconciled(self.batched_expenses, self.batched_payslips)
        reconciliation_lines = self.get_reconciliation_lines_from_accounts(
            (expenses_lines_to_reconcile | payslips_lines_to_reconcile).account_id.ids
        )

        misc_move = reconciliation_lines.debit_move_id.move_id - (self.batched_expenses.account_move_id | self.batched_payslips.move_id)
        self.assertEqual(
            len(misc_move),
            1,
            "Because the expenses & the payslips moves don't have the same account, there should be a misc entry generated",
        )

        misc_move_lines = misc_move.line_ids.sorted('balance')
        expenses_lines_to_reconcile = expenses_lines_to_reconcile.sorted('balance')
        self.assertRecordValues(reconciliation_lines.sorted('amount'), [
            {'amount': 1000.0,  'debit_move_id': misc_move_lines.ids[1],     'credit_move_id': expenses_lines_to_reconcile.ids[9]},
            {'amount': 1001.0,  'debit_move_id': misc_move_lines.ids[2],     'credit_move_id': expenses_lines_to_reconcile.ids[8]},
            {'amount': 1002.0,  'debit_move_id': misc_move_lines.ids[3],     'credit_move_id': expenses_lines_to_reconcile.ids[7]},
            {'amount': 1003.0,  'debit_move_id': misc_move_lines.ids[4],     'credit_move_id': expenses_lines_to_reconcile.ids[6]},
            {'amount': 1004.0,  'debit_move_id': misc_move_lines.ids[5],     'credit_move_id': expenses_lines_to_reconcile.ids[5]},
            {'amount': 1005.0,  'debit_move_id': misc_move_lines.ids[6],     'credit_move_id': expenses_lines_to_reconcile.ids[4]},
            {'amount': 1006.0,  'debit_move_id': misc_move_lines.ids[7],     'credit_move_id': expenses_lines_to_reconcile.ids[3]},
            {'amount': 1007.0,  'debit_move_id': misc_move_lines.ids[8],     'credit_move_id': expenses_lines_to_reconcile.ids[2]},
            {'amount': 1008.0,  'debit_move_id': misc_move_lines.ids[9],     'credit_move_id': expenses_lines_to_reconcile.ids[1]},
            {'amount': 1009.0,  'debit_move_id': misc_move_lines.ids[10],     'credit_move_id': expenses_lines_to_reconcile.ids[0]},
            {'amount': 10045.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': misc_move_lines.ids[0]},
        ])

    @freeze_time('2022-01-25')
    def test_corner_case_batched_payslips_with_same_accounts_between_expenses_and_payslip(self):
        """
        Test that posting the payslip move is properly reconciled with the expenses ones,
        in the case where the payable account is the same for both the payslip & the expenses moves
        """
        # Sets the expense rule on the payroll expense rule
        payable_account_id = self.batched_expenses[0]._get_expense_account_destination()
        self.expense_salary_rule.account_debit = payable_account_id

        self.batched_payslips.compute_sheet()
        self.payslip_run.action_validate()

        self.assertSequenceEqual(
            ['posted'] * 10,
            self.batched_expenses.account_move_id.mapped('state'),
        )

        self.payslip_run.slip_ids.move_id.action_post()
        self.assertEqual(1, len(self.payslip_run.slip_ids.move_id))
        self.assertSequenceEqual(
            ['paid'] * 10,
            self.batched_expenses.mapped('state'),
            "All expense moves should be paid and reconciled with the payslips move",
        )

        # Check reconciliation
        # Get the corresponding account.partial.reconcile lines
        expenses_lines_to_reconcile, payslips_lines_to_reconcile = \
            self.get_all_amls_to_be_reconciled(self.batched_expenses, self.batched_payslips)
        reconciliation_lines = self.get_reconciliation_lines_from_accounts([payable_account_id])

        misc_move = reconciliation_lines.debit_move_id.move_id - (self.batched_expenses.account_move_id | self.batched_payslips.move_id)
        self.assertFalse(
            misc_move,
            "Because the expenses & the payslips moves have the same account, there should be no misc entry generated",
        )

        expenses_lines_to_reconcile = expenses_lines_to_reconcile.sorted('balance')
        self.assertRecordValues(reconciliation_lines.sorted('amount'), [
            {'amount': 1000.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[9]},
            {'amount': 1001.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[8]},
            {'amount': 1002.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[7]},
            {'amount': 1003.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[6]},
            {'amount': 1004.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[5]},
            {'amount': 1005.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[4]},
            {'amount': 1006.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[3]},
            {'amount': 1007.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[2]},
            {'amount': 1008.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[1]},
            {'amount': 1009.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[0]},
        ])

    @freeze_time('2022-01-25')
    def test_corner_case_batched_payslips_with_too_many_different_accounts(self):
        """
        Test that posting the payslip move cannot automatically reconcile but prepares it to be manually reconciled,
        in the case where there would be more than 2 different accounts for the payslip & the expenses moves
        """
        # Unlink the actual moves, so they're re-generated with the new accounts
        self.batched_expenses.account_move_id.button_draft()
        self.batched_expenses.account_move_id.unlink()
        self.batched_expenses.action_reset()

        # Generate a different account for each partner
        default_payable_account = self.env['account.account'].browse(self.batched_expenses[0]._get_expense_account_destination())
        for idx, employee_partner in enumerate(self.batched_expenses.employee_id.work_contact_id.sorted('name')):
            employee_partner.property_account_payable_id = self.env['account.account'].create({
                'name': employee_partner.name,
                'code': f'{default_payable_account.code}00{idx}',
                'account_type': 'liability_payable',
            })
        self.batched_expenses.action_submit()
        self.batched_expenses._do_approve()  # Skip duplicate wizard
        self.post_expenses_with_wizard(self.batched_expenses)
        self.assertEqual(
            10,
            len(self.batched_expenses.account_move_id.line_ids.filtered(lambda line: line.display_type == 'payment_term').account_id),
            "We should now have a different account per expense",
        )

        # Re-link payslips with the expenses, as the reset of the expenses unlinked them
        self.batched_expenses.action_report_in_next_payslip()
        self.batched_payslips.action_payslip_draft()
        self.assertSetEqual(set(self.batched_expenses.payslip_id.ids), set(self.batched_payslips.ids))

        self.batched_payslips.compute_sheet()
        self.payslip_run.action_validate()
        self.assertSequenceEqual(
            ['posted'] * 10,
            self.batched_expenses.account_move_id.mapped('state'),
        )

        self.payslip_run.slip_ids.move_id.action_post()
        self.assertEqual(1, len(self.payslip_run.slip_ids.move_id))
        self.assertSequenceEqual(
            ['posted'] * 10,
            self.batched_expenses.mapped('state'),
            "All expense moves should still be set to 'not_paid'",
        )

        # Check the moves are NOT reconciled
        # Get the corresponding account.partial.reconcile lines
        expenses_lines_to_reconcile, payslips_lines_to_reconcile = \
            self.get_all_amls_to_be_reconciled(self.batched_expenses, self.batched_payslips)
        reconciliation_lines = self.get_reconciliation_lines_from_accounts(
            (expenses_lines_to_reconcile | payslips_lines_to_reconcile).account_id.ids
        )
        self.assertFalse(
            reconciliation_lines,
            "Because the expenses & the payslip moves don't have the same amount, there should be no reconciliation",
        )
        self.assertSequenceEqual(
            ['posted'] * 10,
            self.batched_expenses.mapped('state'),
            "Because the expenses & the payslip moves don't have the same amount, there should be no reconciliation",
        )
        self.assertSequenceEqual(
            ['not_paid'] * 10,
            self.batched_expenses.account_move_id.mapped('payment_state'),
            "Because the expenses & the payslip moves don't have the same amount, there should be no reconciliation",
        )
        self.assertEqual(
            10045.0,
            sum(self.batched_expenses.account_move_id.mapped('amount_residual')),
            "Because the expenses & the payslip moves don't have the same amount, there should be no reconciliation",
        )

        self.assertSequenceEqual(
            [f'I0000000000-{self.batched_payslips.move_id.id}-{min(self.batched_expenses.account_move_id.ids)}'] * 11,
            expenses_lines_to_reconcile.mapped('matching_number') + [payslips_lines_to_reconcile.matching_number],
            "A temporary matching number should still be present on the account move lines to help manually reconcile them"
        )

    @freeze_time('2022-01-25')
    def test_corner_case_batched_payslips_with_different_accounts_mix(self):
        """
        Test that the link is still properly done when payslips are accounted for in batches,
        in the case where there would be 2 different accounts for the payslip & the expenses moves,
        but the accounts difference is only on the expense side
        (mix between `-with_same_accounts_between_expenses_and_payslip` & `-with_too_many_different_accounts`)
        """
        # Sets the payslip move expense line account to be the default expense one
        self.expense_salary_rule.account_debit = self.batched_expenses[0]._get_expense_account_destination()

        # Take one expense and make it use a different account
        different_account_expense = self.batched_expenses[-1]
        different_account_expense_original_payslip = different_account_expense.payslip_id
        different_account_expense.account_move_id.button_draft()
        different_account_expense.account_move_id.unlink()
        different_account = self.env['account.account'].create({
            'name': 'Different account',
            'code': '111111111111111111111111111111111',
            'account_type': 'liability_payable',
        })
        different_account_expense.employee_id.work_contact_id.property_account_payable_id = different_account

        # Put the expense back on the payslip
        self.post_expenses_with_wizard(different_account_expense)
        different_account_expense.action_report_in_next_payslip()
        different_account_expense_original_payslip.action_payslip_draft()
        self.assertEqual(
            different_account_expense_original_payslip.id,
            different_account_expense.payslip_id.id,
            'The expense should be re-linked to a payslip',
        )

        self.batched_payslips.compute_sheet()
        self.payslip_run.action_validate()

        self.assertSequenceEqual(
            ['posted'] * 10,
            self.batched_expenses.account_move_id.mapped('state'),
        )

        self.payslip_run.slip_ids.move_id.action_post()
        self.assertSequenceEqual(
            ['posted'] * 10,
            self.batched_expenses.account_move_id.mapped('state'),
            "All expense moves should be automatically posted when posting the payslip one",
        )

        self.assertEqual(1, len(self.payslip_run.slip_ids.move_id))
        self.assertSequenceEqual(
            ['paid'] * 10,
            self.batched_expenses.mapped('state'),
            "All expense moves should be paid and reconciled with the payslips move",
        )

        # Check reconciliation
        # Get the corresponding account.partial.reconcile lines
        expenses_lines_to_reconcile, payslips_lines_to_reconcile = \
            self.get_all_amls_to_be_reconciled(self.batched_expenses, self.batched_payslips)
        reconciliation_lines = self.get_reconciliation_lines_from_accounts((self.expense_salary_rule.account_debit | different_account).ids)

        misc_move = reconciliation_lines.debit_move_id.move_id - (self.batched_expenses.account_move_id | self.batched_payslips.move_id)
        self.assertEqual(
            len(misc_move),
            1,
            "Because the last expense & the payslips moves don't have the same account, there should be a misc entry generated",
        )
        misc_move_lines = misc_move.line_ids.sorted('balance')
        expenses_lines_to_reconcile = expenses_lines_to_reconcile.sorted('balance')
        # Sorting by name to avoid non-deterministic order of the two last lines, names of the lines sould be "Reimb.." & "Transfer..."
        self.assertRecordValues(reconciliation_lines.sorted(lambda prl: (prl.amount, prl.debit_move_id.name)), [
            {'amount': 1000.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[9]},
            {'amount': 1001.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[8]},
            {'amount': 1002.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[7]},
            {'amount': 1003.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[6]},
            {'amount': 1004.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[5]},
            {'amount': 1005.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[4]},
            {'amount': 1006.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[3]},
            {'amount': 1007.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[2]},
            {'amount': 1008.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': expenses_lines_to_reconcile.ids[1]},
            # Only the last expense is reconciled with a misc move as it uses a different account
            {'amount': 1009.0, 'debit_move_id': payslips_lines_to_reconcile.id, 'credit_move_id': misc_move_lines.ids[0]},
            {'amount': 1009.0, 'debit_move_id': misc_move_lines.ids[1],     'credit_move_id': expenses_lines_to_reconcile.ids[0]},
        ])

    @freeze_time('2022-01-25')
    def test_corner_case_batched_payslips_with_edited_expense_moves(self):
        edited_expense = self.batched_expenses[0]

        # Editing the expense move
        edited_expense.account_move_id.button_draft()
        edited_expense.account_move_id.invoice_line_ids.filtered(lambda aml: aml.product_id == self.product_c).quantity = 2
        self.assertEqual(
            edited_expense.total_amount,
            1000,
            "The move should have a different amount than the expense",
        )
        self.assertEqual(
            edited_expense.account_move_id.amount_total,
            2000,
            "The move should have a different amount than the expense",
        )

        # Post the moves
        self.batched_payslips.compute_sheet()
        self.payslip_run.action_validate()
        self.batched_payslips.move_id.action_post()

        # Check the two moves are NOT reconciled
        # Get the corresponding account.partial.reconcile lines
        expenses_lines_to_reconcile, payslips_lines_to_reconcile = \
            self.get_all_amls_to_be_reconciled(self.batched_expenses, self.batched_payslips)
        reconciliation_lines = self.get_reconciliation_lines_from_accounts(
            (expenses_lines_to_reconcile | payslips_lines_to_reconcile).account_id.ids
        )
        self.assertFalse(
            reconciliation_lines,
            "Because the expense & the payslip moves don't have the same amount, there should be no reconciliation",
        )
        self.assertSequenceEqual(
            ['posted'] * 10,
            self.batched_expenses.mapped('state'),
            "Because the expense & the payslip moves don't have the same amount, there should be no reconciliation",
        )
        self.assertSequenceEqual(
            ['not_paid'] * 10,
            self.batched_expenses.account_move_id.mapped('payment_state'),
            "Because the expense & the payslip moves don't have the same amount, there should be no reconciliation",
        )
        self.assertNotEqual(
            0.0,
            sum(self.batched_expenses.account_move_id.mapped('amount_residual')),
            "Because the expense & the payslip moves don't have the same amount, there should be no reconciliation",
        )

        self.assertSequenceEqual(
            [f'I0000000000-{self.batched_payslips.move_id.id}-{min(self.batched_expenses.account_move_id.ids)}'] * 11,
            expenses_lines_to_reconcile.mapped('matching_number') + [payslips_lines_to_reconcile.matching_number],
            "A temporary matching number should still be present on the account move lines to help manually reconcile them"
        )
