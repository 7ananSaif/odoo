# -*- coding: utf-8 -*-
from freezegun import freeze_time
from contextlib import closing

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import RedirectWarning
from odoo.tests import Form, tagged
from odoo import Command


@tagged('post_install', '-at_install')
class TestReconciliationMatchingRules(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        #################
        # Company setup #
        #################
        cls.other_currency = cls.setup_other_currency('EUR')
        cls.other_currency_2 = cls.setup_other_currency('CAD', rates=[('2016-01-01', 10.0), ('2017-01-01', 20.0)])

        cls.account_rec = cls.company_data['default_account_receivable']
        cls.account_pay = cls.company_data['default_account_payable']
        cls.current_assets_account = cls.env['account.account'].search([
            ('account_type', '=', 'asset_current'),
            ('company_ids', '=', cls.company.id)], limit=1)

        cls.bank_journal = cls.env['account.journal'].search([('type', '=', 'bank'), ('company_id', '=', cls.company.id)], limit=1)
        cls.cash_journal = cls.env['account.journal'].create({'type': 'cash', 'name': 'Cash'})

        cls.tax_account = cls.env['account.account'].create({
            'name': 'TAX_ACC',
            'code': 'TACC',
            'account_type': 'liability_current',
            'reconcile': False,
        })

        cls.tax21 = cls.env['account.tax'].create({
            'name': '21%',
            'type_tax_use': 'purchase',
            'amount': 21,
            'invoice_repartition_line_ids': [
                (0, 0, {'repartition_type': 'base'}),
                (0, 0, {
                    'repartition_type': 'tax',
                    'account_id': cls.tax_account.id,
                }),
            ],
            'refund_repartition_line_ids': [
                (0, 0, {'repartition_type': 'base'}),
                (0, 0, {
                    'repartition_type': 'tax',
                    'account_id': cls.tax_account.id,
                }),
            ],
        })

        cls.partner_1 = cls.env['res.partner'].create({'name': 'partner_1', 'company_id': cls.company.id})
        cls.partner_2 = cls.env['res.partner'].create({'name': 'partner_2', 'company_id': cls.company.id})
        cls.partner_3 = cls.env['res.partner'].create({'name': 'partner_3', 'company_id': cls.company.id})
        cls.partner_agrolait = cls.env['res.partner'].create({'name': 'Agrolait', 'company_id': cls.company.id})

        ###############
        # Rules setup #
        ###############
        cls.rule_1 = cls.env['account.reconcile.model'].create({
            'name': 'button that shouldn\'t be proposed',
            'sequence': 1,
            'match_partner_ids': [],
            'line_ids': [Command.create({'account_id': cls.current_assets_account.id})],
        })
        cls.rule_2 = cls.env['account.reconcile.model'].create({
            'name': 'button to be completed by each test',
            'sequence': 2,
            'match_journal_ids': [(6, 0, [cls.bank_journal.id])],
            'match_label': 'contains',
            'match_label_param': 'fees',
            'line_ids': [Command.create({'account_id': cls.current_assets_account.id})],
        })
        cls.mapping_partner_rule = cls.env['account.reconcile.model'].create({
            'name': 'mapping agrolait',
            'sequence': 100,
            'match_label': 'contains',
            'match_label_param': 'agrolait',
            'line_ids': [Command.create({'partner_id': cls.partner_agrolait.id})],
        })

    def _create_and_post_payment(self, amount=100, memo=None, post=True, partner=True, **kwargs):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
            'partner_type': 'customer',
            'partner_id': self.partner_a.id if partner else False,
            'amount': amount,
            'journal_id': self.company_data['default_journal_bank'].id,
            'memo': memo,
            **kwargs,
        })
        if post:
            payment.action_post()
        return payment

    @classmethod
    def _create_invoice_line(cls, amount, partner, move_type, currency=None, ref=None, name=None, inv_date='2019-09-01'):
        ''' Create an invoice on the fly.'''
        invoice_form = Form(cls.env['account.move'].with_context(default_move_type=move_type, default_invoice_date=inv_date, default_date=inv_date))
        invoice_form.partner_id = partner
        if currency:
            invoice_form.currency_id = currency
        if ref:
            invoice_form.ref = ref
        if name:
            invoice_form.name = name
        with invoice_form.invoice_line_ids.new() as invoice_line_form:
            invoice_line_form.name = 'xxxx'
            invoice_line_form.quantity = 1
            invoice_line_form.price_unit = amount
            invoice_line_form.tax_ids.clear()
        invoice = invoice_form.save()
        invoice.action_post()
        lines = invoice.line_ids
        return lines.filtered(lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable'))

    @classmethod
    def _create_st_line(cls, amount=1000.0, date='2019-01-01', payment_ref='turlututu', **kwargs):
        st_line = cls.env['account.bank.statement.line'].create({
            'journal_id': kwargs.get('journal_id', cls.bank_journal.id),
            'amount': amount,
            'date': date,
            'payment_ref': payment_ref,
            'partner_id': cls.partner_a.id,
            **kwargs,
        })
        return st_line

    @classmethod
    def _create_reconcile_model(cls, **kwargs):
        return cls.env['account.reconcile.model'].create({
            'name': "test",
            **kwargs,
            'line_ids': [
                Command.create({
                    'account_id': cls.company_data['default_account_revenue'].id,
                    'amount_type': 'percentage',
                    'label': f"test {i}",
                    **line_vals,
                })
                for i, line_vals in enumerate(kwargs.get('line_ids', []))
            ],
        })

    @freeze_time('2020-01-01')
    def _check_st_line_matching(self, st_line, expected_values, reconciled_amls=None):
        reconciled_amls = reconciled_amls or []
        self.assertRecordValues(st_line.move_id.line_ids, expected_values)
        if not reconciled_amls:
            return
        for inv_line, rec_aml in zip(st_line.move_id.line_ids.filtered(lambda x: x.account_id.account_type in ('asset_receivable', 'liability_payable')), reconciled_amls):
            if inv_line.debit:
                self.assertEqual(inv_line.matched_credit_ids.credit_move_id, rec_aml)
            else:
                self.assertEqual(inv_line.matched_debit_ids.debit_move_id, rec_aml)

    def test_matching_buttons(self):
        bank_line_1, bank_line_2, cash_line_1 = self.env['account.bank.statement.line'].with_context(auto_statement_processing=True).create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'invoice 2020-01-01',
                'amount': 100,
                'sequence': 1,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'xxxxxfeesxxx',
                'partner_id': self.partner_1.id,
                'amount': 30,
                'sequence': 2,
            },
            {
                'journal_id': self.cash_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'yyyyyfees',
                'amount': -1000,
                'sequence': 1,
            },
        ])
        # no need to call the cron since we passed the contextual key to process the lines automatically
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': False},
        ], reconciled_amls=False)
        self._check_st_line_matching(bank_line_2, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': self.rule_2.id},
        ], reconciled_amls=False)
        self._check_st_line_matching(cash_line_1, [
            {'account_id': self.cash_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.cash_journal.suspense_account_id.id, 'reconcile_model_id': False},
        ], reconciled_amls=False)

    def test_button_with_taxes(self):
        bank_line_1 = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'xxxagrolaitxxfeesxxx',
                'amount': -121,
                'sequence': 1,
            },
        ])
        rule_tax = self.env['account.reconcile.model'].create({
            'name': 'button that includes some taxes on the lines to create',
            'sequence': 1,
            'match_partner_ids': [],
            'line_ids': [Command.create({'account_id': self.current_assets_account.id, 'tax_ids': self.tax21.ids})],
        })
        # push the button
        rule_tax._trigger_reconciliation_model(bank_line_1)
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False, 'partner_id': False, 'balance': -121.0},
            {'account_id': self.current_assets_account.id, 'reconcile_model_id': rule_tax.id, 'partner_id': False, 'balance': 100},
            {'account_id': self.tax_account.id, 'reconcile_model_id': False, 'partner_id': False, 'balance': 21},
        ], reconciled_amls=False)

    def test_partner_mapping(self):
        bank_line_1 = self.env['account.bank.statement.line'].with_context(auto_statement_processing=True).create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'xxxagrolaitxxfeesxxx',
                'amount': 30,
                'sequence': 2,
            },
        ])
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False, 'partner_id': self.partner_agrolait.id},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': self.rule_2.id, 'partner_id': self.partner_agrolait.id},
        ], reconciled_amls=False)

    def test_matching_algorithm(self):
        invoice_line_1 = self._create_invoice_line(100, self.partner_1, 'out_invoice')
        invoice_line_2 = self._create_invoice_line(200, self.partner_1, 'out_invoice')
        invoice_line_3 = self._create_invoice_line(300, self.partner_1, 'in_refund', name="RBILL/2019/09/0013")
        invoice_line_4 = self._create_invoice_line(1000, self.partner_2, 'in_invoice')
        _invoice_line_5 = self._create_invoice_line(1000, self.partner_2, 'in_invoice')
        _invoice_line_6 = self._create_invoice_line(1000, self.partner_2, 'in_invoice')
        invoice_line_7 = self._create_invoice_line(100, self.partner_3, 'out_invoice')
        invoice_line_8 = self._create_invoice_line(600, self.partner_3, 'out_invoice', ref="RF12 3456")
        _invoice_line_9 = self._create_invoice_line(200, self.partner_3, 'out_invoice')
        invoice_line_10 = self._create_invoice_line(200, self.partner_agrolait, 'out_invoice')
        self._create_invoice_line(12345.67, self.partner_2, 'out_invoice')

        bank_line_1, bank_line_2,\
        bank_line_3, bank_line_4,\
        bank_line_5 = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'all open invoices',
                'partner_id': self.partner_1.id,
                'amount': 600,
                'sequence': 1,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': invoice_line_4.move_id.name,
                'partner_id': self.partner_2.id,
                'amount': -1600,
                'sequence': 2,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'approx due amount',
                'narration': 'Communication: RF12 3456',
                'partner_id': self.partner_3.id,
                'amount': 97,
                'sequence': 3,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'RF12 3456',
                'partner_id': self.partner_3.id,
                'amount': 100,
                'sequence': 4,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'transaction_details': {'no partner?': 'yes: agrolait'},
                'ref': 'RF12 3456',
                'amount': 200,
                'sequence': 5,
            },
        ])
        self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=100)
        # the total residual of the partner matches the line amount
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 600.0},
            {'account_id': self.account_rec.id, 'balance': -100.0},
            {'account_id': self.account_rec.id, 'balance': -200.0},
            {'account_id': self.account_pay.id, 'balance': -300.0},
        ], reconciled_amls=[invoice_line_1, invoice_line_2, invoice_line_3])

        # amount isn't the same, but partner and ref are
        self._check_st_line_matching(bank_line_2, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': -1600.0},
            {'account_id': self.account_pay.id, 'balance': 1000.0},
            {'account_id': self.bank_journal.suspense_account_id.id, 'balance': 600.0},  # always the suspense account because it's our way to know the reconciliation isn't over
        ], reconciled_amls=[invoice_line_4, False])

        # partner and amount almost equals the invoice (3% diff allowed)
        self._check_st_line_matching(bank_line_3, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 97.0},
            {'account_id': self.account_rec.id, 'balance': -97.0},
        ], reconciled_amls=[invoice_line_7])

        # amount isn't the same, but partner and ref are
        self._check_st_line_matching(bank_line_4, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 100.0},
            {'account_id': self.account_rec.id, 'balance': -100.0},
        ], reconciled_amls=[invoice_line_8])

        # mapping of agrolait first, then because we have the partner the correct invoice can be found
        self._check_st_line_matching(bank_line_5, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 200.0, 'partner_id': self.partner_agrolait.id},
            {'account_id': self.account_rec.id, 'balance': -200.0, 'partner_id': self.partner_agrolait.id},
        ], reconciled_amls=[invoice_line_10])

    def test_matching_algorithm_for_multiple_invoices(self):
        """Test matching algorithm for multiple invoices with positive statement balance"""

        invoice_line_1 = self._create_invoice_line(800, self.partner_1, 'out_invoice')
        invoice_line_2 = self._create_invoice_line(900, self.partner_1, 'out_invoice')
        invoice_line_3 = self._create_invoice_line(1100, self.partner_1, 'out_invoice')
        invoice_line_4 = self._create_invoice_line(1200, self.partner_1, 'out_invoice')
        invoice_line_5 = self._create_invoice_line(200, self.partner_1, 'out_invoice')
        invoice_line_6 = self._create_invoice_line(200, self.partner_1, 'out_invoice')
        invoice_line_7 = self._create_invoice_line(500, self.partner_1, 'out_invoice')
        invoice_line_8 = self._create_invoice_line(300, self.partner_1, 'out_invoice')
        invoice_line_9 = self._create_invoice_line(150, self.partner_1, 'out_invoice')
        invoice_line_10 = self._create_invoice_line(160, self.partner_1, 'out_invoice')
        invoice_line_11 = self._create_invoice_line(370, self.partner_1, 'out_invoice')

        bank_line_1, bank_line_2,\
        bank_line_3, bank_line_4,\
        bank_line_5 = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': f"{invoice_line_1.move_name} {invoice_line_2.move_name}",
                'partner_id': self.partner_1.id,
                'amount': 1700,
                'sequence': 1,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': f"{invoice_line_3.move_name} and {invoice_line_4.move_name}",
                'partner_id': self.partner_1.id,
                'amount': 2100,
                'sequence': 2,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': f"{invoice_line_5.move_name} and {invoice_line_6.move_name}",
                'partner_id': self.partner_1.id,
                'amount': 200,
                'sequence': 3,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': f"Partner is not set {invoice_line_7.move_name} {invoice_line_8.move_name}",
                'amount': 800,
                'sequence': 4,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': f"{invoice_line_9.move_name} {invoice_line_10.move_name} {invoice_line_11.move_name}",
                'partner_id': self.partner_1.id,
                'amount': 300,
                'sequence': 5,
            },
        ])
        self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=100)

        # payment reference contains invoice numbers of multiple invoices from the same partner, and the total amount matches
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 1700.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_rec.id, 'balance': -800.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_rec.id, 'balance': -900.0, 'partner_id': self.partner_1.id},
        ], reconciled_amls=[invoice_line_1, invoice_line_2])

        # payment reference contains invoice numbers, but the total amount does not match
        self._check_st_line_matching(bank_line_2, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 2100.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_rec.id, 'balance': -1100.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_rec.id, 'balance': -1000.0, 'partner_id': self.partner_1.id},
        ], reconciled_amls=[invoice_line_3, invoice_line_4])

        # Amount is not enough to reconcile both invoices, so only the first one is reconciled
        self._check_st_line_matching(bank_line_3, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 200.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_rec.id, 'balance': -200.0, 'partner_id': self.partner_1.id},
        ], reconciled_amls=[invoice_line_5])

        # payment reference contains invoice number, total amount matches, but the partner is not set
        self._check_st_line_matching(bank_line_4, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 800.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_rec.id, 'balance': -500.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_rec.id, 'balance': -300.0, 'partner_id': self.partner_1.id},
        ], reconciled_amls=[invoice_line_7, invoice_line_8])

        # The payment amount is not enough to fully reconcile all invoices: the first invoice is fully reconciled, the second invoice is partially reconciled, and the third invoice is not reconciled at all.
        self._check_st_line_matching(bank_line_5, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 300.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_rec.id, 'balance': -150.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_rec.id, 'balance': -150.0, 'partner_id': self.partner_1.id},
        ], reconciled_amls=[invoice_line_9, invoice_line_10])

    def test_matching_algorithm_for_multiple_invoices_for_multi_currency(self):
        """Test matching algorithm for multiple invoices with multi currency"""

        invoice_line_1 = self._create_invoice_line(2000, self.partner_1, 'out_invoice', currency=self.other_currency)
        invoice_line_2 = self._create_invoice_line(3000, self.partner_1, 'out_invoice', currency=self.company_data['currency'])

        # Handle when invoices have different currency
        bank_line_1 = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': f"{invoice_line_1.move_name} {invoice_line_2.move_name}",
                'partner_id': self.partner_1.id,
                'amount': 5000,
                'currency_id': self.company_data['currency'].id,
            }
        ])
        self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=100)

        # proposal should only be in the same currency
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'amount_currency': 5000.0, 'partner_id': self.partner_1.id, 'currency_id': self.company_data['currency'].id, 'balance': 5000},
            {'account_id': self.account_rec.id, 'amount_currency': -3000.0, 'partner_id': self.partner_1.id, 'currency_id': self.company_data['currency'].id, 'balance': -3000},
            {'account_id': self.bank_journal.suspense_account_id.id, 'amount_currency': -2000.0, 'partner_id': self.partner_1.id, 'currency_id': self.company_data['currency'].id, 'balance': -2000},
        ], reconciled_amls=[invoice_line_2])

        # add manually the invoice_line_1
        bank_line_1.set_line_bank_statement_line(invoice_line_1.id)

        # Handle when invoices have different currency
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'amount_currency': 5000.0, 'partner_id': self.partner_1.id, 'currency_id': self.company_data['currency'].id, 'balance': 5000},
            {'account_id': self.account_rec.id, 'amount_currency': -3000.0, 'partner_id': self.partner_1.id, 'currency_id': self.company_data['currency'].id, 'balance': -3000},
            {'account_id': self.account_rec.id, 'amount_currency': -2000.0, 'partner_id': self.partner_1.id, 'currency_id': self.other_currency.id, 'balance': -1000},
            {'account_id': self.bank_journal.suspense_account_id.id, 'amount_currency': -1000.0, 'partner_id': self.partner_1.id, 'currency_id': self.company_data['currency'].id, 'balance': -1000},
        ], reconciled_amls=[invoice_line_2, invoice_line_1])

    def test_matching_algorithm_for_multiple_invoices_for_negative_amount(self):
        """Test matching algorithm for multiple invoices with negative statement balance"""
        invoice_line_1 = self._create_invoice_line(111, self.partner_1, 'in_invoice')
        invoice_line_2 = self._create_invoice_line(300, self.partner_1, 'in_invoice')

        bank_line_1 = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': f"{invoice_line_1.move_name} {invoice_line_2.move_name}",
                'partner_id': self.partner_1.id,
                'amount': -411,
            }
        ])
        self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=100)

        # Payment reference contains invoice numbers of multiple invoices from the same partner, and the total amount matches but amount is negative
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': -411.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_pay.id, 'balance': 111.0, 'partner_id': self.partner_1.id},
            {'account_id': self.account_pay.id, 'balance': 300.0, 'partner_id': self.partner_1.id}
        ], reconciled_amls=[invoice_line_1, invoice_line_2])

    def test_matching_rules_with_payment_memo(self):
        """Test matching algorithm for multiple invoices with same ref"""
        invoice_1 = self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO2025/127326425")
        invoice_2 = self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO2025/12237246-13")
        invoice_3 = self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="PAY Admin - SO2025/127326425")
        bank_line_1 = self._create_st_line(amount=200, payment_ref='SO2025/127326425 and SO2025/12237246-13')
        bank_line_1._try_auto_reconcile_statement_lines()
        # Both invoice_1 and invoice_3 refs match the st_line label, so only invoice_2 is reconciled
        self._check_st_line_matching(bank_line_1, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 200.0, 'reconciled': False},
            {'account_id': invoice_2.account_id.id, 'balance': -100.0, 'reconciled': True},
            {'account_id': bank_line_1.journal_id.suspense_account_id.id, 'balance': -100.0, 'reconciled': False},
        ], reconciled_amls=[invoice_2])
        invoice_3.move_id.button_draft()
        invoice_3.move_id.unlink()
        bank_line_1._try_auto_reconcile_statement_lines()
        # Now that invoice_3 is no more there, invoice_1 is the only one to match the rules
        self._check_st_line_matching(bank_line_1, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 200.0, 'reconciled': False},
            {'account_id': invoice_2.account_id.id, 'balance': -100.0, 'reconciled': True},
            {'account_id': invoice_1.account_id.id, 'balance': -100.0, 'reconciled': True},
        ], reconciled_amls=[invoice_2, invoice_1])

    def test_matching_rules_with_wrong_payment_memo(self):
        """Test matching algorithm for multiple invoices with wrong payment_ref."""
        invoice_1 = self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO2025/127326425")
        invoice_2 = self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO2025/12237246-13")
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - paymentSO2025/127326425")
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INVAdminSO2025/127326425")
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO2024/127326425")
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO/2025/127326425")
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin SO2025/127326425")

        bank_line_1 = self._create_st_line(amount=200, payment_ref='SO2025/127326425 & SO2025/12237246-13')
        bank_line_1._try_auto_reconcile_statement_lines()
        # Only payment 1 and 2 match the rules, others shouldn't
        self._check_st_line_matching(bank_line_1, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 200.0, 'reconciled': False},
            {'account_id': invoice_1.account_id.id, 'balance': -100.0, 'reconciled': True},
            {'account_id': invoice_2.account_id.id, 'balance': -100.0, 'reconciled': True},
        ], reconciled_amls=[invoice_2, invoice_1])

    def test_matching_rules_with_duplicate_payment_memo(self):
        """Test that if a statement line contains a string identifying more than 1 invoice, we don't reconcile"""
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO2025/127326425")
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO2025/12237246-13")
        self._create_invoice_line(200, self.partner_a, 'out_invoice', ref="INV Admin - SO2025/127326425 - SO2025/12237246-13")
        self._create_invoice_line(200, self.partner_a, 'out_invoice', ref="Test payment ref")
        self._create_invoice_line(200, self.partner_a, 'out_invoice', ref="Test payment")
        bank_line_1 = self._create_st_line(amount=200, payment_ref='SO2025/127326425 & SO2025/12237246-13')
        bank_line_1._try_auto_reconcile_statement_lines()
        bank_line_2 = self._create_st_line(amount=200, payment_ref='Test payment ref')
        bank_line_2._try_auto_reconcile_statement_lines()
        # We don't have matches, invoice 3 ref is conflicting with invoice 1 and 2
        self.assertRecordValues(bank_line_1.line_ids, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 200.0, 'reconciled': False},
            {'account_id': bank_line_1.journal_id.suspense_account_id.id, 'balance': -200.0, 'reconciled': False},
        ])
        # 2 invoices match, don't reconcile
        self.assertRecordValues(bank_line_2.line_ids, [
            {'account_id': bank_line_2.journal_id.default_account_id.id, 'balance': 200.0, 'reconciled': False},
            {'account_id': bank_line_2.journal_id.suspense_account_id.id, 'balance': -200.0, 'reconciled': False},
        ])

    def test_matching_rules_with_same_ref_on_st_line_and_aml(self):
        """Test reconciliation if move_id of st_line have the same ref"""
        payment = self._create_and_post_payment(amount=100, memo="Test label ref")
        bank_line_1 = self._create_st_line(amount=100, payment_ref='Test label ref')
        bank_line_1.move_id.ref = "Test label ref"
        bank_line_1._try_auto_reconcile_statement_lines()
        self.assertRecordValues(bank_line_1.line_ids, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': payment.outstanding_account_id.id, 'balance': -100.0, 'reconciled': True},
        ])

    def test_matching_rules_for_full_match_on_aml_ref(self):
        """Test reconciliation full match on aml ref"""
        self._create_and_post_payment(amount=100, memo="000100000", partner=False)
        bank_line_1 = self._create_st_line(amount=100, payment_ref='000000001000000000123')
        bank_line_1._try_auto_reconcile_statement_lines()
        # As aml.ref is only a part of a word in st_line.payment_ref, we can't reconcile
        self.assertRecordValues(bank_line_1.line_ids, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': bank_line_1.journal_id.suspense_account_id.id, 'balance': -100.0, 'reconciled': False},
        ])

    def test_matching_rules_with_structured_ref(self):
        """Test reconciliation with structured ref, to be sure special char like '+' are well escaped in the query regex"""
        payment = self._create_and_post_payment(amount=100, memo="+++123/456/7890+++")
        self._create_and_post_payment(amount=100, memo="+++123/456/7891+++")
        bank_line_1 = self._create_st_line(amount=100, payment_ref='+++123/456/7890+++')
        bank_line_1._try_auto_reconcile_statement_lines()
        self.assertRecordValues(bank_line_1.line_ids, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': payment.outstanding_account_id.id, 'balance': -100.0, 'reconciled': True},
        ])

    def test_matching_rules_with_multiple_payments_with_same_ref(self):
        """Test reconciliation with structured ref, to be sure special char like '+' are well escaped in the query regex"""
        self._create_and_post_payment(amount=100, memo="+++123/456/7890+++")
        self._create_and_post_payment(amount=100, memo="+++123/456/7890+++")
        self._create_and_post_payment(amount=100, memo="+++123/456/7891+++")
        self._create_and_post_payment(amount=100, memo="+++123/456/7891+++")
        bank_line_1 = self._create_st_line(amount=200, payment_ref='+++123/456/7890+++')
        bank_line_1._try_auto_reconcile_statement_lines()
        self.assertRecordValues(bank_line_1.line_ids, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 200.0, 'reconciled': False},
            {'account_id': bank_line_1.journal_id.suspense_account_id.id, 'balance': -200.0, 'reconciled': False},
        ])

    def test_matching_rules_with_long_ref(self):
        """Test reconciliation with long ref. As it's long, it shouldn't match with the first rule but the second"""
        payment = self._create_and_post_payment(amount=100, memo="SO/2025/127/326/425/222/11-01")
        self._create_and_post_payment(amount=100, memo="SO/2025/127/326/425/222/11-02")
        bank_line_1 = self._create_st_line(amount=100, payment_ref='SO/2025/127/326/425/222/11-01')
        bank_line_1._try_auto_reconcile_statement_lines()
        self.assertRecordValues(bank_line_1.line_ids, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': payment.outstanding_account_id.id, 'balance': -100.0, 'reconciled': True},
        ])

    def test_perfect_match_on_move_name(self):
        """Test reconciliation for perfect match on move name"""
        payment = self._create_and_post_payment(amount=100, partner=False)
        bank_line_1 = self._create_st_line(amount=100, payment_ref=f"{payment.move_id.name}23")
        bank_line_1._try_auto_reconcile_statement_lines()
        self.assertRecordValues(bank_line_1.line_ids, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': bank_line_1.journal_id.suspense_account_id.id, 'balance': -100.0, 'reconciled': False},
        ])

    def test_matching_rules_payment_regex(self):
        """Test if the regex matching statement lines & invoices is working properly"""
        # Good format
        invoice_1 = self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO2025/127326425")
        invoice_2 = self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO2025/12237246-13")
        invoice_3 = self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV Admin - SO/2025/127326426")
        invoice_4 = self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="INV/2025/127326425 - Bob")
        invoice_5 = self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="Invoice for Bob with id - py_aesadasea123asdb")
        # Wrong format
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="Admin SaleOrder2025/127326425")
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="Admin SO2025/127326425")
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="Admin SO2025/63173462/234/567/890-11")
        self._create_invoice_line(100, self.partner_a, 'out_invoice', ref="Invoice for Bob with id py_aesadasea123asdb")

        bank_line_1 = self._create_st_line(amount=100, payment_ref='SO2025/127326425 - Odoo Partner: Admin')
        bank_line_2 = self._create_st_line(amount=100, payment_ref='Odoo Partner: Admin - SO2025/12237246-13')
        bank_line_3 = self._create_st_line(amount=100, payment_ref='SO/2025/127326426 For admin')
        bank_line_4 = self._create_st_line(amount=100, payment_ref='INV/2025/127326425 paid on 2025')
        bank_line_5 = self._create_st_line(amount=100, payment_ref='py_aesadasea123asdb')
        self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=100)

        # Everything should be reconciled
        self._check_st_line_matching(bank_line_1, [
            {'account_id': bank_line_1.journal_id.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': invoice_1.account_id.id, 'balance': -100.0, 'reconciled': True},
        ], reconciled_amls=[invoice_1])
        self._check_st_line_matching(bank_line_2, [
            {'account_id': bank_line_2.journal_id.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': invoice_2.account_id.id, 'balance': -100.0, 'reconciled': True},
        ], reconciled_amls=[invoice_2])
        self._check_st_line_matching(bank_line_3, [
            {'account_id': bank_line_3.journal_id.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': invoice_3.account_id.id, 'balance': -100.0, 'reconciled': True},
        ], reconciled_amls=[invoice_3])
        self._check_st_line_matching(bank_line_4, [
            {'account_id': bank_line_4.journal_id.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': invoice_4.account_id.id, 'balance': -100.0, 'reconciled': True},
        ], reconciled_amls=[invoice_4])
        self._check_st_line_matching(bank_line_5, [
            {'account_id': bank_line_5.journal_id.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': invoice_5.account_id.id, 'balance': -100.0, 'reconciled': True},
        ], reconciled_amls=[invoice_5])

    def test_auto_rule_creation_and_matching(self):
        account_a = self.env['account.account'].create({
            'name': "Custom Account A",
            'code': "010101",
            'account_type': "asset_current",
        })
        account_b = self.env['account.account'].create({
            'name': "Custom Account B",
            'code': "020202",
            'account_type': "asset_current",
        })
        bank_stmt_line_1 = self._create_st_line(amount=10, payment_ref='VISA PAYMENT RENT ON 2020-01-01 FOR JAN')
        bank_stmt_line_2 = self._create_st_line(amount=100, payment_ref='VISA PAYMENT RENT ON 2020-02-01 FOR FEB')

        bank_stmt_line_1.set_account_bank_statement_line(bank_stmt_line_1.line_ids[-1].id, account_a.id)
        bank_stmt_line_2.set_account_bank_statement_line(bank_stmt_line_2.line_ids[-1].id, account_a.id)
        # Assert that the reconciliation model has been created with the correct parameters.
        reco_model = self.env['account.reconcile.model'].search([
            ('created_automatically', '=', True),
            ('match_label', '=', 'match_regex'),
            ('match_label_param', '=', 'VISA\\ PAYMENT\\ RENT\\ ON\\ \\d+\\-\\d+\\-\\d+\\ FOR\\ '),
            ('match_partner_ids', '=', self.partner_a.ids),
            ('line_ids.account_id', '=', account_a.id),
        ])
        self.assertTrue(reco_model.exists())

        bank_stmt_line_3 = self._create_st_line(amount=1000, payment_ref='VISA PAYMENT RENT ON 2020-03-01 FOR MAR')
        bank_stmt_line_3._try_auto_reconcile_statement_lines()
        # Assert that the created model will be used as a suggestion.
        self.assertEqual(bank_stmt_line_3.line_ids[-1].reconcile_model_id.id, reco_model.id)

        # Assert that the rule is deleted when another account is selected while having a suggestion.
        bank_stmt_line_3.set_account_bank_statement_line(bank_stmt_line_3.line_ids[-1].id, account_b.id)
        self.assertFalse(reco_model.exists())

    def test_auto_rule_creation_and_matching_with_structured_reference(self):
        account_a = self.env['account.account'].create({
            'name': "Custom Account A",
            'code': "010101",
            'account_type': "asset_current",
        })
        bank_stmt_line_1 = self._create_st_line(amount=100, payment_ref='TAX +++123/12345/1234+++ 100 EUR')
        bank_stmt_line_2 = self._create_st_line(amount=200, payment_ref='TAX +++123/12345/1234+++ 200 EUR')

        bank_stmt_line_1.set_account_bank_statement_line(bank_stmt_line_1.line_ids[-1].id, account_a.id)
        bank_stmt_line_2.set_account_bank_statement_line(bank_stmt_line_2.line_ids[-1].id, account_a.id)
        # Assert that the reconciliation model and that the structured reference has been perserved.
        reco_model = self.env['account.reconcile.model'].search([
            ('created_automatically', '=', True),
            ('match_label', '=', 'match_regex'),
            ('match_label_param', '=', 'TAX\\ \\+\\+\\+\\d+/\\d+/\\d+\\+\\+\\+\\ \\d+\\ EUR'),
        ])
        self.assertTrue(reco_model.exists())

        bank_stmt_line_3 = self._create_st_line(amount=300, payment_ref='TAX +++123/12345/1234+++ 300 EUR')
        bank_stmt_line_3._try_auto_reconcile_statement_lines()
        # Assert that the created model will be used as a suggestion.
        self.assertEqual(bank_stmt_line_3.line_ids[-1].reconcile_model_id.id, reco_model.id)

    def test_auto_rule_creation_and_matching_case_insensitive_label_less_than_10(self):
        account_a = self.env['account.account'].create({
            'name': "Custom Account A",
            'code': "010101",
            'account_type': "asset_current",
        })
        bank_stmt_line_1 = self._create_st_line(amount=100, payment_ref='Rent')
        bank_stmt_line_2 = self._create_st_line(amount=200, payment_ref='RENT')

        bank_stmt_line_1.set_account_bank_statement_line(bank_stmt_line_1.line_ids[-1].id, account_a.id)
        bank_stmt_line_2.set_account_bank_statement_line(bank_stmt_line_2.line_ids[-1].id, account_a.id)
        # Assert that the reconciliation model has been created even if the label is not exactly 10 characters long.
        reco_model = self.env['account.reconcile.model'].search([
            ('created_automatically', '=', True),
            ('match_label', '=', 'match_regex'),
            ('match_label_param', '=', 'RENT'),
        ])
        self.assertTrue(reco_model.exists())

        bank_stmt_line_3 = self._create_st_line(amount=300, payment_ref='rent')
        bank_stmt_line_3._try_auto_reconcile_statement_lines()
        # Assert that the created model will be used as a suggestion.
        self.assertEqual(bank_stmt_line_3.line_ids[-1].reconcile_model_id.id, reco_model.id)

    def test_auto_rule_creation_unreconciled_lines_to_match(self):
        account_a = self.env['account.account'].create({
            'name': "Custom Account A",
            'code': "010101",
            'account_type': "asset_current",
        })
        line_to_match_1 = self._create_st_line(amount=100, payment_ref='Payment')
        line_to_match_2 = self._create_st_line(amount=200, payment_ref='Payment')
        unreconciled_line = self._create_st_line(amount=300, payment_ref='Payment')  # To stay unreconciled.

        line_to_match_1.set_account_bank_statement_line(line_to_match_1.line_ids[-1].id, account_a.id)
        # Assert that the reconciliation model has been created and set_account_bank_statement_line returns the existing
        # unreconciled lines that can now match with the new rule.
        lines_to_reload = line_to_match_2.set_account_bank_statement_line(line_to_match_2.line_ids[-1].id, account_a.id)
        self.assertEqual(lines_to_reload, unreconciled_line)

    def test_common_substring_handles_none_safely(self):
        """Test that the common_substring function handles None values safely."""
        account_a, account_b = self.env['account.account'].create([{
            'name': "Edge Case Account A",
            'code': "040404",
            'account_type': "asset_current",
        }, {
            'name': "Temporary Account B",
            'code': "050505",
            'account_type': "asset_current",
        }])

        payment_refs = [
            'Hello',
            'Test',
            'Demo',
        ]

        lines = []
        for ref in payment_refs:
            line = self._create_st_line(amount=1.0, payment_ref=ref)
            lines.append(line)

        for i in range(2):
            lines[i].set_account_bank_statement_line(lines[i].line_ids[-1].id, account_a.id)

        lines[2].set_account_bank_statement_line(lines[2].line_ids[-1].id, account_b.id)
        lines[2].delete_reconciled_line(lines[2].line_ids[-1].id)
        lines[2].set_account_bank_statement_line(lines[2].line_ids[-1].id, account_a.id)
        # Assert that the reconciliation model has not been created and no crash occurs.
        reco_model = self.env['account.reconcile.model'].search([
            ('match_label', '=', 'match_regex'),
            ('match_label_param', '=', ''),
        ])
        self.assertFalse(reco_model.exists())

    def test_auto_rule_creation_and_matching_for_lines_without_payment_ref(self):
        """ Assert bank statement lines without a payment reference will not affect the matching algorithm """
        account_a = self.env['account.account'].create({
            'name': "Custom Account A",
            'code': "010101",
            'account_type': "asset_current",
        })
        bank_stmt_line_1 = self._create_st_line(amount=100, payment_ref=None)
        bank_stmt_line_2 = self._create_st_line(amount=200, payment_ref=None)
        bank_stmt_line_3 = self._create_st_line(amount=300, payment_ref='VISA PAYMENT 300 EUR')
        bank_stmt_line_4 = self._create_st_line(amount=400, payment_ref='VISA PAYMENT 400 EUR')

        bank_stmt_line_1.set_account_bank_statement_line(bank_stmt_line_1.line_ids[-1].id, account_a.id)
        bank_stmt_line_2.set_account_bank_statement_line(bank_stmt_line_2.line_ids[-1].id, account_a.id)
        bank_stmt_line_3.set_account_bank_statement_line(bank_stmt_line_3.line_ids[-1].id, account_a.id)
        bank_stmt_line_4.set_account_bank_statement_line(bank_stmt_line_4.line_ids[-1].id, account_a.id)
        # Assert that the reconciliation model has been created even when not all the recent bank statement lines have
        # a payment reference.
        reco_model = self.env['account.reconcile.model'].search([
            ('match_label', '=', 'match_regex'),
            ('match_label_param', '=', 'VISA\\ PAYMENT\\ \\d+\\ EUR'),
        ])
        self.assertTrue(reco_model.exists())

    def test_multiple_auto_rule_creation_with_same_account_for_different_payment_ref(self):
        """ Test that when setting same account on statement lines with different payment ref will create multiple reco model """
        account_a = self.env['account.account'].create({
            'name': "Custom Account A",
            'code': "010101",
            'account_type': "asset_current",
        })
        bank_stmt_line_1 = self._create_st_line(amount=100, payment_ref='DINNER PAYMENT 100 EUR')
        bank_stmt_line_2 = self._create_st_line(amount=200, payment_ref='DINNER PAYMENT 200 EUR')
        bank_stmt_line_3 = self._create_st_line(amount=300, payment_ref='VISA PAYMENT 300 EUR')
        bank_stmt_line_4 = self._create_st_line(amount=400, payment_ref='VISA PAYMENT 400 EUR')

        bank_stmt_line_1.set_account_bank_statement_line(bank_stmt_line_1.line_ids[-1].id, account_a.id)
        bank_stmt_line_2.set_account_bank_statement_line(bank_stmt_line_2.line_ids[-1].id, account_a.id)
        bank_stmt_line_3.set_account_bank_statement_line(bank_stmt_line_3.line_ids[-1].id, account_a.id)
        bank_stmt_line_4.set_account_bank_statement_line(bank_stmt_line_4.line_ids[-1].id, account_a.id)

        reco_models = self.env['account.reconcile.model'].search([
            ('match_label', '=', 'match_regex'),
            ('match_label_param', 'in', ['DINNER\\ PAYMENT\\ \\d+\\ EUR', 'VISA\\ PAYMENT\\ \\d+\\ EUR']),
        ])
        self.assertTrue(reco_models.exists())
        self.assertEqual(len(reco_models), 2, "Reco model should be created for both type of payment refs")

    def test_only_one_auto_rule_creation_for_same_payment_ref(self):
        """ Test that when setting same account on more than two statement lines with same payment ref will not create more than one
            reco model """
        account_a = self.env['account.account'].create({
            'name': "Custom Account A",
            'code': "010101",
            'account_type': "asset_current",
        })
        bank_stmt_line_1 = self._create_st_line(amount=100, payment_ref='OFFICE RENT PAYMENT 100 EUR')
        bank_stmt_line_2 = self._create_st_line(amount=200, payment_ref='OFFICE RENT PAYMENT 200 EUR')
        bank_stmt_line_3 = self._create_st_line(amount=300, payment_ref='OFFICE RENT PAYMENT 300 EUR')
        bank_stmt_line_4 = self._create_st_line(amount=400, payment_ref='OFFICE RENT PAYMENT 400 EUR')

        bank_stmt_line_1.set_account_bank_statement_line(bank_stmt_line_1.line_ids[-1].id, account_a.id)
        bank_stmt_line_2.set_account_bank_statement_line(bank_stmt_line_2.line_ids[-1].id, account_a.id)
        bank_stmt_line_3.set_account_bank_statement_line(bank_stmt_line_3.line_ids[-1].id, account_a.id)
        bank_stmt_line_4.set_account_bank_statement_line(bank_stmt_line_4.line_ids[-1].id, account_a.id)

        reco_models = self.env['account.reconcile.model'].search([
            ('match_label', '=', 'match_regex'),
            ('match_label_param', 'in', ['OFFICE\\ RENT\\ PAYMENT\\ \\d+\\ EUR']),
        ])
        self.assertTrue(reco_models.exists())
        self.assertEqual(len(reco_models), 1, "Only one Reco model should be created for same payment refs")

    def test_discount_amount(self):
        _invoice_line_1 = self._create_invoice_line(100, self.partner_1, 'out_invoice')
        invoice_line_2 = self._create_invoice_line(100, self.partner_1, 'out_invoice')
        bank_line_1 = self.env['account.bank.statement.line'].with_context(auto_statement_processing=True).create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-02-01',
                'payment_ref': 'no clear identification of the paid invoice',
                'partner_id': self.partner_1.id,
                'amount': 95,
                'sequence': 1,
            }
        ])

        bank_line_1._try_auto_reconcile_statement_lines()
        # no proposal, since there are several possibilities
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 95.0},
            {'account_id': self.bank_journal.suspense_account_id.id, 'balance': -95.0},
        ], reconciled_amls=[])

        # add early payment discount info
        invoice_line_2.discount_date = '2020-01-15'
        invoice_line_2.discount_balance = 95.0

        bank_line_1._try_auto_reconcile_statement_lines()
        # early payment not matching because payment date is after the discount date
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 95.0},
            {'account_id': self.bank_journal.suspense_account_id.id, 'balance': -95.0},
        ], reconciled_amls=[])

        # add early payment discount info
        bank_line_1.date = '2020-01-14'
        bank_line_1._try_auto_reconcile_statement_lines()
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 95.0},
            {'account_id': self.account_rec.id, 'balance': -95.0},
        ], reconciled_amls=[invoice_line_2])

    def test_early_payment_discount_partial_payment(self):
        invoice = self.init_invoice(move_type='out_invoice', partner=self.partner_a, invoice_date='2019-09-01', amounts=[100])
        invoice.invoice_payment_term_id = self.env.ref('account.account_payment_term_30days_early_discount')
        invoice.action_post()
        st_line = self._create_st_line(amount=50, payment_ref=invoice.name)
        st_line._try_auto_reconcile_statement_lines()
        self.assertEqual(invoice.payment_state, 'partial')
        self._check_st_line_matching(st_line, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 50.0},
            {'account_id': self.account_rec.id, 'balance': -50.0}
        ])

    def test_no_partner_ambiguity(self):
        _invoice_line_1 = self._create_invoice_line(600, self.partner_1, 'out_invoice', ref="RF12 3456")
        _invoice_line_2 = self._create_invoice_line(600, self.partner_2, 'out_invoice', ref="RF12 3456")
        bank_line = self.env['account.bank.statement.line'].with_context(auto_statement_processing=True).create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'RF12 3456',
                'amount': 600,
                'sequence': 1,
            },
        ])
        # no proposal, since there are several possibilities
        self._check_st_line_matching(bank_line, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 600.0},
            {'account_id': self.bank_journal.suspense_account_id.id, 'balance': -600.0},
        ], reconciled_amls=[])

    def test_move_name_caba_tax_account(self):
        self.env.company.tax_exigibility = True
        tax_account = self.company_data['default_account_tax_sale']
        tax_account.reconcile = True

        caba_tax = self.env['account.tax'].create({
            'name': "CABA",
            'amount_type': 'percent',
            'amount': 20.0,
            'tax_exigibility': 'on_payment',
            'cash_basis_transition_account_id': self.safe_copy(tax_account).id,
            'invoice_repartition_line_ids': [
                Command.create({
                    'repartition_type': 'base',
                }),
                Command.create({
                    'repartition_type': 'tax',
                    'account_id': tax_account.id,
                }),
            ],
        })

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2021-07-01',
            'invoice_line_ids': [
                Command.create({
                    'name': "test",
                    'price_unit': 100,
                    'tax_ids': [Command.set(caba_tax.ids)],
                }),
            ]
        })
        invoice.action_post()
        self.env['account.bank.statement.line'].with_context(auto_statement_processing=True).create({
            'amount': 100.0,
            'date': '2019-01-01',
            'payment_ref': invoice.name,
            'journal_id': self.company_data['default_journal_bank'].id,
            })
        caba_move = invoice.tax_cash_basis_created_move_ids
        self.assertEqual(caba_move.line_ids[0].move_name, caba_move.name)

    def test_widget_available_for_line(self):
        """
            Tests what the reconcileModelPerStatementLineId (js side) will receive
            A reco model is valid for a statement line if the value to filter is valid on the statement line or if
            it is not specified on the model
            Used to know which reconcile model to show in the list on the statement line
        """
        self.env['account.reconcile.model'].search([]).unlink()  # Don't want it to appear in suggestion
        bank_line_1, bank_line_2, bank_line_3 = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'Line 1',
                'amount': -121,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'Line 2',
                'partner_id': self.partner_1.id,
                'amount': -121,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'xxxagrolaitxxfeesxxx',
                'partner_id': self.partner_1.id,
                'amount': 500,
            },
        ])

        model_everywhere = self.env['account.reconcile.model'].create(
            {
                'name': "Shown everywhere",
                'line_ids': [
                    Command.create({'account_id': self.current_assets_account.id}),
                    Command.create({'account_id': self.account_pay.id}),
                ],
            },
        )
        self.env['account.reconcile.model'].create(
            {
                'name': "Never shown because no Counterpart wit account",
                'line_ids': [Command.create({'partner_id': self.partner_1.id})],
            },
        )
        model_partner_a = self.env['account.reconcile.model'].create(
            {
                'name': "Needs partner 1",
                'match_partner_ids': self.partner_1.ids,
                'line_ids': [Command.create({'account_id': self.current_assets_account.id})],
            },
        )
        model_amount = self.env['account.reconcile.model'].create(
            {
                'name': "Needs amount",
                'match_amount': 'greater',
                'match_amount_min': 200,
                'line_ids': [Command.create({'account_id': self.current_assets_account.id})],
            },
        )
        model_partner_a_amount = self.env['account.reconcile.model'].create(
            {
                'name': "Needs amount and partner 1",
                'match_amount': 'greater',
                'match_amount_min': 200,
                'match_partner_ids': self.partner_1.ids,
                'line_ids': [Command.create({'account_id': self.current_assets_account.id})],
            },
        )
        model_label = self.env['account.reconcile.model'].create(
            {
                'name': "Needs label",
                'match_label': 'contains',
                'match_label_param': 'fees',
                'line_ids': [Command.create({'account_id': self.current_assets_account.id})],
            },
        )

        models_per_line = self.env['account.reconcile.model'].with_context(lang='en_US').get_available_reconcile_model_per_statement_line(
            (bank_line_1 + bank_line_2 + bank_line_3).ids
        )
        self.assertEqual(
            models_per_line[bank_line_1.id],
            [
                {'id': model_everywhere.id, 'display_name': "Shown everywhere"},
            ],
            "Does not match the amounts or partners"
        )
        self.assertEqual(
            models_per_line[bank_line_2.id],
            [
                {'id': model_everywhere.id, 'display_name': "Shown everywhere"},
                {'id': model_partner_a.id, 'display_name': "Needs partner 1"},
            ],
            "Only match the partner"
        )
        self.assertEqual(
            models_per_line[bank_line_3.id],
            [
                {'id': model_everywhere.id, 'display_name': "Shown everywhere"},
                {'id': model_partner_a.id, 'display_name': "Needs partner 1"},
                {'id': model_amount.id, 'display_name': 'Needs amount'},
                {'id': model_partner_a_amount.id, 'display_name': 'Needs amount and partner 1'},
                {'id': model_label.id, 'display_name': 'Needs label'},
            ],
            "Match the partner, the amount and the label"
        )
        model_label.active = False
        bank_line_3_models = self.env['account.reconcile.model'].with_context(lang='en_US') \
            .get_available_reconcile_model_per_statement_line((bank_line_3).ids)
        self.assertNotIn(
            model_label.id,
            bank_line_3_models[bank_line_3.id],
            "Should not display archived reconcile models"
        )

    def test_modify_reco_model_apply_on_statement_line(self):
        """
        This test will check that modifying a reco model will change the suggestion on statement lines
        """
        bank_line_1, bank_line_2 = self.env['account.bank.statement.line'].with_context(auto_statement_processing=True).create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'fees',
                'amount': 100,
            },
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'blblbl',
                'amount': 100,
            },
        ])
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': self.rule_2.id},
        ], reconciled_amls=False)

        self.rule_2.match_label_param = 'blblbl'
        self._check_st_line_matching(bank_line_1, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': False},
        ], reconciled_amls=False)
        self._check_st_line_matching(bank_line_2, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': self.rule_2.id},
        ], reconciled_amls=False)

    def test_create_reco_model_apply_on_statement_line(self):
        bank_line = self.env['account.bank.statement.line'].with_context(auto_statement_processing=True).create([{
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'blblbl',
                'amount': 100,
            }]
        )

        self._check_st_line_matching(bank_line, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': False},
        ], reconciled_amls=False)

        new_rule = self.env['account.reconcile.model'].create({
            'name': 'new rule',
            'sequence': 3,
            'match_journal_ids': [Command.set([self.bank_journal.id])],
            'match_label': 'contains',
            'match_label_param': 'blblbl',
            'line_ids': [Command.create({'account_id': self.current_assets_account.id})],
        })

        self._check_st_line_matching(bank_line, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': new_rule.id},
        ], reconciled_amls=False)

    def test_archive_reco_model(self):
        bank_line = self.env['account.bank.statement.line'].with_context(auto_statement_processing=True).create([{
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'blblbl',
                'amount': 100,
            }]
        )

        self._check_st_line_matching(bank_line, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': False},
        ], reconciled_amls=False)

        new_rule = self.env['account.reconcile.model'].create({
            'name': 'new rule',
            'match_journal_ids': [Command.set(self.bank_journal.ids)],
            'match_label': 'contains',
            'match_label_param': 'blblbl',
            'line_ids': [Command.create({'account_id': self.current_assets_account.id})],
        })

        self._check_st_line_matching(bank_line, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': new_rule.id},
        ], reconciled_amls=False)

        new_rule.action_archive()
        self._check_st_line_matching(bank_line, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': False},
        ], reconciled_amls=False)

    def test_copy_reco_model_created_automatically(self):
        rule = self.env['account.reconcile.model'].create({
            'name': 'new rule',
            'match_journal_ids': [Command.set(self.bank_journal.ids)],
            'match_label': 'contains',
            'match_label_param': 'blblbl',
            'line_ids': [Command.create({'account_id': self.current_assets_account.id})],
            'created_automatically': True,
        })
        copied_rule = rule.copy()
        self.assertFalse(copied_rule.created_automatically)

    def test_get_common_substring_of_labels(self):
        """
        Test the _get_common_substring helper method.
        It should return the longest common substring if len>10,
        or if all normalised labels are identical, the normalised label.
        Else, return None.
        """
        # Long (>=10) common substring
        long_common_refs = [x + ' is Gamora.' for x in ('Where', 'Who', 'Why')]
        long_common_bl = [self._create_st_line(payment_ref=x) for x in long_common_refs]
        self.assertEqual(long_common_bl[0]._get_common_substring([x.payment_ref for x in long_common_bl]), '\\ IS\\ GAMORA\\.')
        # Short (<10) but identical normalised string
        short_normalised_refs = ['Odoo ' + str(x) for x in (18, 19, 9000)]
        short_normalised_bl = [self._create_st_line(payment_ref=x) for x in short_normalised_refs]
        self.assertEqual(short_normalised_bl[0]._get_common_substring([x.payment_ref for x in short_normalised_bl]), r'ODOO\ \d+')
        # Short (<10) non-identical normalised string
        short_common_refs = ['Great ' + x for x in ('power', 'responsibility')]
        short_common_bl = [self._create_st_line(payment_ref=x) for x in short_common_refs]
        self.assertEqual(short_common_bl[0]._get_common_substring([x.payment_ref for x in short_common_bl]), None)

    def test_apply_reco_model_with_bad_counterpart_regex(self):
        bad_regex_model = self.env['account.reconcile.model'].create({
            'name': 'new rule',
            'line_ids': [
                Command.create({
                    'account_id': self.current_assets_account.id,
                    'amount_type': 'regex',
                    'amount_string': r'missing parentheses: \d+',
                    'label': 'Should raise a (caught) IndexError',
                }),
                Command.create({
                    'account_id': self.current_assets_account.id,
                    'amount_type': 'regex',
                    'amount_string': r'does not capture a float value: ([a-z]+)',
                    'label': 'Should raise a (caught) AttributeError',
                }),
                Command.create({
                    'account_id': self.current_assets_account.id,
                    'amount_type': 'regex',
                    'amount_string': r'can capture an empty value: ([\d]*)',
                    'label': 'Can raise a (caught) AttributeError',
                }),
            ],
        })

        bank_line_1 = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'missing parentheses: 1234',
                'amount': 1234,
            },
        ])
        bank_line_2 = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'does not capture a float value: notafloatvalue',
                'amount': 1234,
            },
        ])
        bank_line_3 = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'can capture an empty value:    ',
                'amount': 1234,
            },
        ])

        with self.assertRaises(RedirectWarning, msg="The regex has to capture the amount in parenthesis"):
            bad_regex_model._trigger_reconciliation_model(bank_line_1)
        with self.assertRaises(RedirectWarning, msg="The regex has to capture a float value"):
            bad_regex_model._trigger_reconciliation_model(bank_line_2)
        with self.assertRaises(RedirectWarning, msg="The regex cannot capture an empty value"):
            bad_regex_model._trigger_reconciliation_model(bank_line_3)

    def test_no_reco_model_on_receivable_payable_button(self):
        bank_stmt_line_1 = self._create_st_line(amount=10, payment_ref='This is a test')
        bank_stmt_line_2 = self._create_st_line(amount=100, payment_ref='This is a test')

        bank_stmt_line_1.set_account_bank_statement_line(bank_stmt_line_1.line_ids[-1].id, self.company_data['default_account_receivable'].id)
        bank_stmt_line_2.set_account_bank_statement_line(bank_stmt_line_2.line_ids[-1].id, self.company_data['default_account_receivable'].id)
        bank_stmt_line_3 = self._create_st_line(amount=1000, payment_ref='This is a test')
        # Check that no reconciliation model is set on the suspense line as we set a receivable account manually
        self.assertFalse(bank_stmt_line_3.line_ids[-1].reconcile_model_id.id)

    def test_apply_reco_model_other_currency(self):
        new_journal = self.env['account.journal'].create({
            'name': 'test',
            'code': 'TBNK',
            'type': 'bank',
            'currency_id': self.other_currency.id,
        })

        bank_stmt_line = self._create_st_line(amount=100, journal_id=new_journal.id)

        reco_model = self.env['account.reconcile.model'].create({
            'name': 'New reco model',
            'match_journal_ids': [Command.set([new_journal.id])],
            'match_label': 'contains',
            'match_label_param': 'turlututu',
            'line_ids': [Command.create({
                'account_id': self.current_assets_account.id,
                'amount_type': 'percentage',
                'amount': 100,
                'label': 'test',
            })],
        })

        self._check_st_line_matching(bank_stmt_line, [
            {'account_id': new_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': new_journal.suspense_account_id.id, 'reconcile_model_id': reco_model.id},
        ], reconciled_amls=False)
        reco_model._trigger_reconciliation_model(bank_stmt_line)

        self.assertRecordValues(bank_stmt_line.line_ids, [
            {'account_id': bank_stmt_line.journal_id.default_account_id.id, 'balance': 50, 'amount_currency': 100, 'reconciled': False},
            {'account_id': self.current_assets_account.id, 'balance': -50.0, 'amount_currency': -100, 'reconciled': False},
        ])

    def test_reco_model_with_activities(self):
        activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
        reco_model = self.env['account.reconcile.model'].create({
            'name': 'new rule',
            'match_label': 'contains',
            'match_label_param': 'fees',
            'next_activity_type_id': activity_type_id,
        })

        st_line = self.env['account.bank.statement.line'].create({
            'journal_id': self.bank_journal.id,
            'date': '2020-01-01',
            'payment_ref': 'fees',
            'amount': 100,
        })
        reco_model._trigger_reconciliation_model(st_line)
        self.assertEqual(st_line.activity_ids.activity_type_id.id, activity_type_id)

    def test_match_amount_in_between_neg_amount(self):
        bank_stmt_line = self._create_st_line(amount=-1500)
        between_rule = self.env['account.reconcile.model'].create(
            {
                'name': "Between neg amount",
                'match_amount': 'between',
                'match_amount_min': -1000,
                'match_amount_max': -2000,
                'line_ids': [Command.create({'account_id': self.current_assets_account.id})],
            },
        )
        self._check_st_line_matching(bank_stmt_line, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': between_rule.id},
        ], reconciled_amls=False)

        # Check if it works both ways
        between_rule.update({
            'match_amount_min': -2000,
            'match_amount_max': -1000,
        })
        self._check_st_line_matching(bank_stmt_line, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': between_rule.id},
        ], reconciled_amls=False)

    def test_create_multiple_reco_model_with_same_account(self):
        account_a = self.env['account.account'].create({
            'name': "Custom Account A",
            'code': "010101",
            'account_type': "asset_current",
        })
        st_line_1 = self._create_st_line(amount=100, payment_ref='This is a test')
        st_line_2 = self._create_st_line(amount=100, payment_ref='This is a test')
        st_line_3 = self._create_st_line(amount=1000, payment_ref='This is a test')
        st_line_1.set_account_bank_statement_line(st_line_1.line_ids[-1].id, account_a.id)
        st_line_2.set_account_bank_statement_line(st_line_2.line_ids[-1].id, account_a.id)
        # Check that a reco model has been created with the right name
        self.assertEqual(st_line_3.line_ids[-1].reconcile_model_id.name, "Custom Account A")

        st_line_4 = self._create_st_line(amount=100, payment_ref='Rent bla bla bla')
        st_line_5 = self._create_st_line(amount=100, payment_ref='Rent bla bla bla')
        st_line_6 = self._create_st_line(amount=100, payment_ref='Rent bla bla bla')
        st_line_4.set_account_bank_statement_line(st_line_4.line_ids[-1].id, account_a.id)
        st_line_5.set_account_bank_statement_line(st_line_5.line_ids[-1].id, account_a.id)
        # Check that a reco model has been created with the right name
        self.assertEqual(st_line_6.line_ids[-1].reconcile_model_id.name, "Custom Account A")

    def test_matching_outstanding_accounts(self):
        another_journal_id = self.env['account.journal'].create({'name': 'another journal', 'type': 'bank', 'code': 'BNKX'}).id
        self._create_and_post_payment(amount=100, memo="SO2025/127326425", journal_id=another_journal_id)
        bank_stmt_line = self._create_st_line(amount=100, payment_ref='SO2025/127326425')
        bank_stmt_line._try_auto_reconcile_statement_lines()
        # no proposal, since the journal of the outstanding payment is different than the one from the statement line
        self.assertRecordValues(bank_stmt_line.line_ids, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'balance': -100.0, 'reconciled': False},
        ])

        payment_2 = self._create_and_post_payment(amount=100, memo="SO2025/127326425 - INV/2025/05/0656")
        bank_stmt_line._try_auto_reconcile_statement_lines()
        # matching done, since a part of the commmunication (split on ' - ') of the outstanding payment can be found in the transaction
        self.assertRecordValues(bank_stmt_line.line_ids, [
            {'account_id': self.bank_journal.default_account_id.id, 'balance': 100.0, 'reconciled': False},
            {'account_id': payment_2.outstanding_account_id.id, 'balance': -100.0, 'reconciled': True},
        ])

    def test_ref_included_in_another(self):
        _invoice_line_1 = self._create_invoice_line(600, self.partner_1, 'out_invoice', ref="INV/2025/08/10")
        invoice_line_2 = self._create_invoice_line(600, self.partner_2, 'out_invoice', ref="INV/2025/08/101")
        bank_line = self.env['account.bank.statement.line'].with_context(auto_statement_processing=True).create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'INV/2025/08/101',
                'amount': 600,
                'sequence': 1,
            },
        ])
        # _invoice_line_1 and invoice_line_2 both found, but the ref of _invoice_line_1 isn't a complete word in
        # payment_ref, so it should be rejected and only invoice_line_2 kept and reconciled since there's no
        # ambiguity anymore
        self._check_st_line_matching(bank_line, [
            {'account_id': bank_line.journal_id.default_account_id.id, 'balance': 600.0, 'reconciled': False},
            {'account_id': invoice_line_2.account_id.id, 'balance': -600.0, 'reconciled': True},
        ], reconciled_amls=[invoice_line_2])

    def test_negative_contains_matching_rule(self):
        rule = self.env['account.reconcile.model'].create({
            'name': 'Not contains rule',
            'sequence': 3,
            'match_label': 'not_contains',
            'match_label_param': 'test',
            'line_ids': [Command.create({
                'account_id': self.current_assets_account.id,
                'amount_type': 'percentage',
                'amount': 100,
                'label': 'Counterpart',
            })],
        })
        st_line = self.env['account.bank.statement.line'].with_context(auto_statement_processing=True).create({
            'journal_id': self.bank_journal.id,
            'date': '2020-01-01',
            'payment_ref': 'some payment ref',
            'amount': 100,
        })
        self._check_st_line_matching(st_line, [
            {'account_id': self.bank_journal.default_account_id.id, 'reconcile_model_id': False},
            {'account_id': self.bank_journal.suspense_account_id.id, 'reconcile_model_id': rule.id},
        ], reconciled_amls=False)

    # TODO add tests on multi companies
    # TODO add tests on multi currencies
    # TODO add tests on taxes
    # TODO add tests on proposed buttons / applicability (conditions of appearance)
    # TODO add tests on auto_reconcile trigger

#    def test_no_amount_check_keep_first(self):
#        """ In case the reconciliation model doesn't check the total amount of the candidates,
#        we still don't want to suggest more than are necessary to match the statement.
#        For example, if a statement line amounts to 250 and is to be matched with three invoices
#        of 100, 200 and 300 (retrieved in this order), only 100 and 200 should be proposed.
#        """
#        self.bank_line_2.amount = 250
#        self.bank_line_1.partner_id = None
#
#        self._check_statement_matching(self.rule_1, {
#            self.bank_line_1: {},
#            self.bank_line_2: {
#                'amls': self.invoice_line_1 + self.invoice_line_2,
#                'model': self.rule_1,
#                'status': 'write_off',
#            },
#        })
#
#    def test_no_amount_check_exact_match(self):
#        """ If a reconciliation model finds enough candidates for a full reconciliation,
#        it should still check the following candidates, in case one of them exactly
#        matches the amount of the statement line. If such a candidate exist, all the
#        other ones are disregarded.
#        """
#        self.bank_line_2.amount = 300
#        self.bank_line_1.partner_id = None
#
#        self._check_statement_matching(self.rule_1, {
#            self.bank_line_1: {},
#            self.bank_line_2: {
#                'amls': self.invoice_line_3,
#                'model': self.rule_1,
#                'status': 'write_off',
#            },
#        })
#
