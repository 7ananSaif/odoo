# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from odoo import Command
from odoo.addons.account_accountant.tests.test_account_bank_statement import TestAccountBankStatement
from odoo.tests import tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestBatchPayment(TestAccountBankStatement):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a bank journal
        cls.journal = cls.company_data['default_journal_bank']
        cls.batch_deposit_method = cls.env.ref('account_batch_payment.account_payment_method_batch_deposit')
        cls.batch_deposit = cls.journal.inbound_payment_method_line_ids.filtered(lambda l: l.code == 'batch_payment')
        cls.other_currency = cls.setup_other_currency('EUR')

    @classmethod
    def create_payment(cls, partner, amount, **kwargs):
        """ Create a batch deposit payment """
        payment = cls.env['account.payment'].create({
            'journal_id': cls.journal.id,
            'payment_type': 'inbound',
            'date': time.strftime('%Y') + '-07-15',
            'amount': amount,
            'partner_id': partner.id,
            'partner_type': 'customer',
            **kwargs,
        })
        payment.action_post()
        return payment

    @classmethod
    def _create_st_line(cls, amount=1000.0, date='2019-01-01', payment_ref='turlututu', **kwargs):
        return cls.env['account.bank.statement.line'].create({
            'journal_id': cls.journal.id,
            'amount': amount,
            'date': date,
            'payment_ref': payment_ref,
            'partner_id': cls.partner_a.id,
            **kwargs,
        })

    def test_zero_amount_payment(self):
        zero_payment = self.create_payment(self.partner_a, 0, payment_method_line_id=self.batch_deposit.id)
        batch_vals = {
            'journal_id': self.journal.id,
            'payment_ids': [(4, zero_payment.id, None)],
            'payment_method_id': self.batch_deposit_method.id,
        }
        self.assertRaises(ValidationError, self.env['account.batch.payment'].create, batch_vals)

    def test_exchange_diff_batch_payment(self):
        """
            This test will do a basic case where the company is in US Dollars but the st_line and the payment are in
            another currencies. Between the moment where we created the batch payment and the st_line a difference of
            rates happens and so an exchange diff is created.
        """
        self.other_currency = self.setup_other_currency('EUR', rates=[('2016-01-03', 2.0), ('2017-01-03', 1.0)])
        payment = self.create_payment(
            partner=self.partner_a,
            amount=100,
            date='2017-01-02',
            journal_id=self.company_data['default_journal_bank'].id,
            currency_id=self.other_currency.id,
        )
        payment.create_batch_payment()

        st_line = self._create_st_line(
            100.0,
            date='2017-01-05',
        )
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {
                'account_id': st_line.journal_id.default_account_id.id,
                'amount_currency': 100.0,
                'currency_id': self.company_data['currency'].id,
                'balance': 100.0,
                'reconciled': False,
            },
            {
                'account_id': payment.outstanding_account_id.id,
                'amount_currency': -100.0,
                'currency_id': self.other_currency.id,
                'balance': -100.0,
                'reconciled': True,
            },
        ])
        exchange_move = st_line.line_ids[1].matched_debit_ids.exchange_move_id
        self.assertRecordValues(exchange_move.line_ids, [
            {
                'account_id': payment.outstanding_account_id.id,
                'currency_id': self.other_currency.id,
                'balance': 50.0,
            },
            {
                'account_id': self.env.company.income_currency_exchange_account_id.id,
                'currency_id': self.other_currency.id,
                'balance': -50.0,
            },
        ])

    def test_partner_account_batch_payments_with_journal_entry(self):
        """ Test the account for batch payments with a linked journal entry """
        for payment_type, account_a, account_b in [
            ('inbound', self.partner_a.property_account_receivable_id, self.partner_b.property_account_receivable_id),
            ('outbound', self.partner_a.property_account_payable_id, self.partner_b.property_account_payable_id),
        ]:
            outstanding_account = self.env['account.payment']._get_outstanding_account(payment_type)
            self.batch_deposit.payment_account_id = outstanding_account
            payment_1 = self.env['account.payment'].create({
                'date': '2015-01-01',
                'payment_type': payment_type,
                'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
                'partner_id': self.partner_a.id,
                'payment_method_line_id': self.batch_deposit.id,
                'amount': 100.0,
            })
            payment_2 = self.env['account.payment'].create({
                'date': '2015-01-01',
                'payment_type': payment_type,
                'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
                'partner_id': self.partner_b.id,
                'payment_method_line_id': self.batch_deposit.id,
                'amount': 200.0,
            })
            payments = payment_1 + payment_2
            payments.action_post()
            batch = self.env['account.batch.payment'].create({
                'batch_type': payment_type,
                'journal_id': self.journal.id,
                'payment_ids': [Command.set(payments.ids)],
                'payment_method_id': self.batch_deposit_method.id,
            })
            batch.validate_batch()
            st_line_amount = 300.0 if payment_type == 'inbound' else -300.0
            st_line = self.env['account.bank.statement.line'].create({
                'journal_id': self.journal.id,
                'amount': st_line_amount,
                'date': '2015-01-01',
                'payment_ref': batch.name,
            })
            st_line.set_batch_payment_bank_statement_line(batch.id)
            bank_account = self.journal.default_account_id
            if payment_type == 'inbound':
                self.assertRecordValues(payments.move_id.line_ids.sorted('balance'), [
                    {'account_id': account_b.id, 'partner_id': self.partner_b.id, 'balance': -200.0},
                    {'account_id': account_a.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_b.id, 'balance': 200.0},
                ])
                self.assertRecordValues(st_line.move_id.line_ids.sorted('balance'), [
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_b.id, 'balance': -200.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
                    {'account_id': bank_account.id, 'partner_id': False, 'balance': 300.0},
                ])
            else:
                self.assertRecordValues(payments.move_id.line_ids.sorted('balance'), [
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_b.id, 'balance': -200.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
                    {'account_id': account_a.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
                    {'account_id': account_b.id, 'partner_id': self.partner_b.id, 'balance': 200.0},
                ])
                self.assertRecordValues(st_line.move_id.line_ids.sorted('balance'), [
                    {'account_id': bank_account.id, 'partner_id': False, 'balance': -300.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_b.id, 'balance': 200.0},
                ])

    def test_bank_rec_widget_batch_payment_with_entries(self):
        payment = self.create_payment(self.partner_a, 100, journal_id=self.company_data['default_journal_bank'].id)
        payment.create_batch_payment()

        st_line = self._create_st_line(amount=100)
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'name': st_line.payment_ref, 'amount_currency': 100.0, 'currency_id': self.company_data['currency'].id, 'balance': 100.0, 'reconciled': False},
            {'account_id': payment.journal_id.inbound_payment_method_line_ids.payment_account_id.id, 'name': payment.journal_id.inbound_payment_method_line_ids[0].name, 'amount_currency': -100.0, 'currency_id': self.company_data['currency'].id, 'balance': -100.0, 'reconciled': True},
        ])
        self.assertEqual(st_line.line_ids.reconciled_lines_ids, payment.move_id.line_ids.filtered(lambda x: x.account_id.account_type == 'asset_current'))

    def test_bank_rec_widget_batch_payment_delete_payment(self):
        payment = self.create_payment(self.partner_a, 100, payment_method_line_id=self.batch_deposit.id)
        payment.create_batch_payment()

        st_line = self._create_st_line(amount=100)
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)

        # When removing the payment line, the payment should go back to in_process but the batch remains untouched
        st_line.delete_reconciled_line(st_line.line_ids[-1].id)
        self.assertEqual(payment.state, 'in_process')

    def test_batch_reconciliation_multiple_installments_payment_term(self):
        """ Test reconciliation of payments for multiple installments payment term lines """
        payment_term = self.env['account.payment.term'].create({
            'name': "20-80_payment_term",
            'company_id': self.company_data['company'].id,
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 20, 'nb_days': 0}),
                Command.create({'value': 'percent', 'value_amount': 80, 'nb_days': 20}),
            ],
        })
        invoice = self.init_invoice('out_invoice', partner=self.partner_a, amounts=[1000.0])
        invoice.invoice_payment_term_id = payment_term
        invoice.action_post()
        # register payment for the first installment
        payment_1 = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'amount': 200.0,
            'payment_date': '2015-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        payment_1.create_batch_payment()
        st_line_1 = self._create_st_line(amount=200.0, date='2015-01-01', partner_id=False)
        st_line_1.set_batch_payment_bank_statement_line(payment_1.batch_payment_id.id)

        self.assertRecordValues(st_line_1.move_id.line_ids.sorted('balance'), [
            {'balance': -200.0},
            {'balance': 200.0},
        ])

        # register payment for the second installment
        payment_2 = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'amount': 800.0,
            'payment_date': '2015-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        payment_2.create_batch_payment()
        st_line_2 = self._create_st_line(amount=800.0, date='2015-01-01', partner_id=False)
        st_line_2.set_batch_payment_bank_statement_line(payment_2.batch_payment_id.id)

        self.assertRecordValues(st_line_2.move_id.line_ids.sorted('balance'), [
            {'balance': -800.0},
            {'balance': 800.0},
        ])
        self.assertRecordValues(invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term').sorted('balance'), [
            {'balance': 200.0, 'amount_residual': 0.0, 'reconciled': True},
            {'balance': 800.0, 'amount_residual': 0.0, 'reconciled': True},
        ])


@tagged('post_install', '-at_install')
class TestBatchPaymentAccountingOnly(TestBatchPayment):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        if cls.env['ir.module.module']._get('accountant').state != 'installed':
            cls.skipTest(cls, "This class tests payment without entries, which happens only when Accounting is installed")

    def test_partner_account_batch_payments_without_journal_entry(self):
        """ Test that account receivable is used for inbound payments and account payable for outbound ones
            when no journal entry is linked to the payment
        """
        for payment_type, account_a, account_b in [
            ('inbound', self.partner_a.property_account_receivable_id, self.partner_b.property_account_receivable_id),
            ('outbound', self.partner_a.property_account_payable_id, self.partner_b.property_account_payable_id),
        ]:
            payment_1 = self.env['account.payment'].create({
                'date': '2015-01-01',
                'payment_type': payment_type,
                'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
                'partner_id': self.partner_a.id,
                'payment_method_line_id': self.batch_deposit.id,
                'amount': 100.0,
            })
            payment_2 = self.env['account.payment'].create({
                'date': '2015-01-01',
                'payment_type': payment_type,
                'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
                'partner_id': self.partner_b.id,
                'payment_method_line_id': self.batch_deposit.id,
                'amount': 200.0,
            })
            payments = payment_1 + payment_2
            payments.action_post()
            batch = self.env['account.batch.payment'].create({
                'batch_type': payment_type,
                'journal_id': self.journal.id,
                'payment_ids': [Command.set(payments.ids)],
                'payment_method_id': self.batch_deposit_method.id,
            })
            batch.validate_batch()
            st_line_amount = 300.0 if payment_type == 'inbound' else -300.0
            st_line = self.env['account.bank.statement.line'].create({
                'journal_id': self.journal.id,
                'amount': st_line_amount,
                'date': '2015-01-01',
                'payment_ref': batch.name,
            })
            st_line.set_batch_payment_bank_statement_line(batch.id)
            bank_account = self.journal.default_account_id
            if payment_type == 'inbound':
                self.assertRecordValues(st_line.move_id.line_ids.sorted('balance'), [
                    {'account_id': account_b.id, 'partner_id': self.partner_b.id, 'balance': -200.0},
                    {'account_id': account_a.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
                    {'account_id': bank_account.id, 'partner_id': False, 'balance': 300.0},
                ])
            else:
                self.assertRecordValues(st_line.move_id.line_ids.sorted('balance'), [
                    {'account_id': bank_account.id, 'partner_id': False, 'balance': -300.0},
                    {'account_id': account_a.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
                    {'account_id': account_b.id, 'partner_id': self.partner_b.id, 'balance': 200.0},
                ])

    def test_bank_rec_widget_batch_with_epd_without_entries(self):
        st_line = self._create_st_line(180.0, date='2019-01-05')
        early_pay_acc = self.env.company.account_journal_early_pay_discount_loss_account_id
        invoice_lines_with_epd = self._create_invoice_line(
            'out_invoice',
            invoice_date='2019-01-01',
            invoice_payment_term_id=self.early_payment_term.id,
            invoice_line_ids=[{'price_unit': 100.0}],
        ) + self._create_invoice_line(
            'out_invoice',
            invoice_date='2019-01-01',
            invoice_payment_term_id=self.early_payment_term.id,
            invoice_line_ids=[{'price_unit': 100.0}],
        )
        payments = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice_lines_with_epd.move_id.ids,
        ).create({
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()

        batch = self.env['account.batch.payment'].create({
                'batch_type': payments[0].payment_type,
                'journal_id': self.journal.id,
                'payment_ids': [Command.set(payments.ids)],
                'payment_method_id': self.batch_deposit_method.id,
            })
        batch.validate_batch()

        st_line.set_batch_payment_bank_statement_line(payments.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 180.0, 'balance': 180.0, 'reconciled': False},
            {'account_id': invoice_lines_with_epd[0].account_id.id, 'amount_currency': -100.0, 'balance': -100.0, 'reconciled': True},
            {'account_id': early_pay_acc.id, 'amount_currency': 10.0, 'balance': 10.0, 'reconciled': False},
            {'account_id': invoice_lines_with_epd[1].account_id.id, 'amount_currency': -100.0, 'balance': -100.0, 'reconciled': True},
            {'account_id': early_pay_acc.id, 'amount_currency': 10.0, 'balance': 10.0, 'reconciled': False},
        ])
        self.assertEqual(payments.mapped('state'), ['paid', 'paid'])
        self.assertEqual(batch.state, 'reconciled')

        st_line.delete_reconciled_line(st_line.line_ids[1].id)

        self.assertEqual(payments[0].state, 'in_process')
        self.assertEqual(batch.state, 'sent')

    def test_bank_rec_widget_batch_payment_without_entries(self):
        payment = self.create_payment(self.partner_a, 100, payment_method_line_id=self.batch_deposit.id)
        payment.create_batch_payment()

        st_line = self._create_st_line(amount=100)
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'name': st_line.payment_ref, 'amount_currency': 100.0, 'currency_id': self.company_data['currency'].id, 'balance': 100.0, 'reconciled': False},
            {'account_id': self.partner_a.property_account_receivable_id.id, 'name': payment.name, 'amount_currency': -100.0, 'currency_id': self.company_data['currency'].id, 'balance': -100.0, 'reconciled': False},
        ])

    def test_bank_rec_widget_batch_payment_without_entries_link_to_move(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 100,
                }),
            ],
        })
        invoice.action_post()
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids
        ).create({
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()

        payment.create_batch_payment()
        st_line = self._create_st_line(amount=100)
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 100.0, 'balance': 100.0, 'reconciled': False},
            {'account_id': invoice.line_ids[-1].account_id.id, 'amount_currency': -100.0, 'balance': -100.0, 'reconciled': True},
        ])
        self.assertEqual(st_line.line_ids.reconciled_lines_ids, payment.invoice_ids.line_ids.filtered(lambda x: x.account_id.account_type == 'asset_receivable'))

        st_line.delete_reconciled_line(st_line.line_ids[-1].id)
        self.assertEqual(payment.state, 'in_process')
        self.assertEqual(invoice.payment_state, 'in_payment')

    def test_bank_rec_widget_batch_move_link_to_multiple_payment_without_entries(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        invoice.action_post()
        payment_1 = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'amount': 400,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        payment_2 = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'amount': 600,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()

        (payment_1 + payment_2).create_batch_payment()
        st_line = self._create_st_line(amount=1000)
        st_line.set_batch_payment_bank_statement_line(payment_1.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 1000.0, 'balance': 1000.0, 'reconciled': False},
            {'account_id': invoice.line_ids[-1].account_id.id, 'amount_currency': -400.0, 'balance': -400.0, 'reconciled': True},
            {'account_id': invoice.line_ids[-1].account_id.id, 'amount_currency': -600.0, 'balance': -600.0, 'reconciled': True},
        ])
        st_line.delete_reconciled_line(st_line.line_ids[-1].id)
        self.assertEqual(payment_1.state, 'paid')
        self.assertEqual(payment_2.state, 'in_process')
        self.assertEqual(invoice.payment_state, 'in_payment')

    def test_bank_rec_widget_batch_one_move_multiple_payment_without_entries(self):
        invoice_1 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        invoice_1.action_post()
        invoice_2 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        invoice_2.action_post()

        payments = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=(invoice_1 + invoice_2).ids,
        ).create({
            'amount': 2000,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        payments.create_batch_payment()
        st_line = self._create_st_line(amount=2000)
        st_line.set_batch_payment_bank_statement_line(payments.batch_payment_id.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 2000.0, 'balance': 2000.0, 'reconciled': False},
            {'account_id': invoice_1.line_ids[-1].account_id.id, 'amount_currency': -1000.0, 'balance': -1000.0, 'reconciled': True},
            {'account_id': invoice_2.line_ids[-1].account_id.id, 'amount_currency': -1000.0, 'balance': -1000.0, 'reconciled': True},
        ])

    def test_bank_rec_widget_batch_one_move_multiple_payment_without_entries_grouped(self):
        invoice_1 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        invoice_1.action_post()
        invoice_2 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        invoice_2.action_post()

        payments = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=(invoice_1 + invoice_2).ids,
        ).create({
            'amount': 2000,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
            'group_payment': True,
        })._create_payments()
        payments.create_batch_payment()
        st_line = self._create_st_line(amount=2000)
        st_line.set_batch_payment_bank_statement_line(payments.batch_payment_id.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 2000.0, 'balance': 2000.0, 'reconciled': False},
            {'account_id': invoice_1.line_ids[-1].account_id.id, 'amount_currency': -1000.0, 'balance': -1000.0, 'reconciled': True},
            {'account_id': invoice_2.line_ids[-1].account_id.id, 'amount_currency': -1000.0, 'balance': -1000.0, 'reconciled': True},
        ])

    def test_bank_rec_widget_batch_without_entries_grouped_with_bills(self):
        bills_1 = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        bills_1.action_post()
        bills_2 = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        bills_2.action_post()

        payments = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=(bills_1 + bills_2).ids,
        ).create({
            'amount': 2000,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
            'group_payment': True,
        })._create_payments()
        payments.create_batch_payment()
        st_line = self._create_st_line(amount=-2000)
        st_line.set_batch_payment_bank_statement_line(payments.batch_payment_id.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': -2000.0, 'balance': -2000.0, 'reconciled': False},
            {'account_id': bills_1.line_ids[-1].account_id.id, 'amount_currency': 1000.0, 'balance': 1000.0, 'reconciled': True},
            {'account_id': bills_2.line_ids[-1].account_id.id, 'amount_currency': 1000.0, 'balance': 1000.0, 'reconciled': True},
        ])

    def test_bank_rec_widget_batch_with_epd_with_exch_diff_without_entries(self):
        """ Tests a batch payment of a grouped payment with an amount too large for:
                - 1 invoice with an early payment discount AND exchange diff
                - 1 invoice with an early payment discount
            During reconciliation, a payment with move should be created for the first invoice (to correctly handle the EPD),
            the second invoice should correctly be added to the widget, and the surplus should be added as a payment.
        """
        chf_currency = self.setup_other_currency('CHF', rates=[('2016-01-01', 2.0), ('2019-01-03', 4.0)])
        st_line = self._create_st_line(200.0, date='2019-01-05', foreign_currency_id=chf_currency.id)
        early_pay_acc = self.env.company.account_journal_early_pay_discount_loss_account_id
        invoice_with_exch_diff = self._create_invoice_line(
            'out_invoice',
            invoice_date='2019-01-01',
            invoice_payment_term_id=self.early_payment_term.id,
            invoice_line_ids=[{'price_unit': 100.0}],
            currency_id=chf_currency.id,
        )
        invoice_without_exch_diff = self._create_invoice_line(
            'out_invoice',
            invoice_date='2019-01-04',
            invoice_payment_term_id=self.early_payment_term.id,
            invoice_line_ids=[{'price_unit': 100.0}],
            currency_id=chf_currency.id,
        )
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=(invoice_with_exch_diff + invoice_without_exch_diff).move_id.ids,
        ).create({
            'group_payment': True,
            'amount': 200,
            'payment_date': '2019-01-04',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        outstanding_account = self.env['account.payment']._get_outstanding_account(payment.payment_type)

        batch = self.env['account.batch.payment'].create({
                'batch_type': payment.payment_type,
                'journal_id': self.journal.id,
                'payment_ids': [Command.set(payment.ids)],
                'payment_method_id': self.batch_deposit_method.id,
            })
        batch.validate_batch()
        self.assertEqual(batch.amount, 50.0)

        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id,                'amount_currency': 200.0,   'balance': 200.0,   'reconciled': False},
            # The first invoice and payment have been changed into a payment with move to handle the exchange diff. The next line comes from that move.
            {'account_id': outstanding_account.id,                                  'amount_currency': -90.0,   'balance': -22.5,   'reconciled': True},
            # The 2 following lines correspond to the second invoice + EPD.
            {'account_id': invoice_without_exch_diff.account_id.id,                 'amount_currency': -100.0,  'balance': -25.0,   'reconciled': True},
            {'account_id': early_pay_acc.id,                                        'amount_currency': 10.0,    'balance': 2.5,     'reconciled': False},
            # The remaining amount from the payment is added as is.
            {'account_id': payment.partner_id.property_account_receivable_id.id,   'amount_currency': -20.0,   'balance': -5.0,    'reconciled': False},
            {'account_id': st_line.journal_id.suspense_account_id.id,               'amount_currency': -600.0,  'balance': -150.0,  'reconciled': False},
        ])
        self.assertEqual(payment.state, 'paid')
        self.assertEqual(batch.state, 'reconciled')
        self.assertEqual(payment.amount, 110.0, "The creation of the payment with move during reconciliation should have diminished the grouped payment amount.")
