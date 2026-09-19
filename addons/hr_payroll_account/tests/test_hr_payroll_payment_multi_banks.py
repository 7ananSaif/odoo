from odoo import Command
from odoo.tests import tagged, Form

from .test_hr_payroll_account import TestHrPayrollAccountCommon


@tagged('post_install', '-at_install')
class TestHrPayrollPaymentMultiAccount(TestHrPayrollAccountCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.credit_account = cls.env['account.account'].create({
            'name': 'Salary Payble',
            'code': '2301',
            'reconcile': True,
            'account_type': 'liability_current',
        })
        cls.env['hr.salary.rule'].create({
            'name': 'Net Salary',
            'amount_select': 'code',
            'amount_python_compute': 'result = categories["BASIC"] + categories["ALW"] + categories["DED"]',
            'code': 'NET',
            'category_id': cls.env.ref('hr_payroll.NET').id,
            'sequence': 10,
            'account_credit': cls.credit_account.id,
            'struct_id': cls.hr_structure_softwaredeveloper.id,
            'employee_move_line': True,
        })

        # Two bank accounts for John
        bank1 = cls.env['res.partner.bank'].create({
            'acc_number': '111-222',
            'partner_id': cls.hr_employee_john.work_contact_id.id,
            'allow_out_payment': True,
        })
        bank2 = cls.env['res.partner.bank'].create({
            'acc_number': '333-444',
            'partner_id': cls.hr_employee_john.work_contact_id.id,
            'allow_out_payment': True,
        })
        cls.hr_employee_john.bank_account_ids = [Command.set([bank1.id, bank2.id])]

        # Salary distribution: 40% to bank1, 60% to bank2
        cls.hr_employee_john.salary_distribution = {
            str(bank1.id): {
                'sequence': 1,
                'amount': 40.0,
                'amount_is_percentage': True,
            },
            str(bank2.id): {
                'sequence': 2,
                'amount': 60.0,
                'amount_is_percentage': True,
            },
        }

        account = cls.env['account.account'].search([('code', '=', '230000')])

        cls.hr_payslip_john.journal_id.default_account_id = account.id

        cls.hr_payslip_john.action_refresh_from_work_entries()
        cls.bank1, cls.bank2 = bank1, bank2

    def test_payment_multiple_bank_accounts(self):
        """ Payslip with multiple bank accounts should generate multiple payments correctly """

        # Validate payslip
        self.hr_payslip_john.action_payslip_done()
        self.assertEqual(self.hr_payslip_john.state, 'validated')

        # Post the move
        self.hr_payslip_john.move_id.action_post()
        self.assertEqual(self.hr_payslip_john.move_id.state, 'posted')

        # Register payment action
        action_register_payment = self.hr_payslip_john.action_register_payment()
        action_register_payment["context"]["hr_payroll_payment_register"] = True

        wizard = Form.from_action(self.env, action_register_payment)
        action_create_payment = wizard.save().action_create_payments()

        # Extract payment IDs from the action domain
        payment_ids = action_create_payment["domain"][0][2]
        payments = self.env['account.payment'].browse(payment_ids).filtered(lambda p: p.payment_type == 'outbound')

        # Check we generated 2 payments
        self.assertEqual(len(payments), 2, "Expected 2 outbound payments for 2 bank accounts")

        total = self.hr_payslip_john.move_id.amount_total
        expected1 = round(total * 0.40, 2)
        expected2 = round(total * 0.60, 2)

        # Assert amounts & bank account mapping
        payment_by_bank = {p.partner_bank_id.id: p.amount for p in payments}
        self.assertAlmostEqual(payment_by_bank[self.bank1.id], expected1, msg="Bank1 amount incorrect")
        self.assertAlmostEqual(payment_by_bank[self.bank2.id], expected2, msg="Bank2 amount incorrect")
