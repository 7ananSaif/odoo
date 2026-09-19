from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged
from odoo.addons.account_online_synchronization.tests.common import AccountOnlineSynchronizationCommon


@tagged('post_install', '-at_install')
class TestAccountMissingTransactionsWizard(AccountOnlineSynchronizationCommon):
    """ Tests the account journal missing transactions wizard. """

    @patch('odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._fetch_odoo_fin')
    def test_fetch_missing_transaction(self, patched_fetch_odoofin):
        self.account_online_link.state = 'connected'
        patched_fetch_odoofin.side_effect = [
            {
                'transactions': [self._create_one_online_transaction(
                    transaction_identifier='ABCD01',
                    date='2023-07-06', foreign_currency_code='EGP', amount_currency=8.0
                )],
            },
            {
                'transactions': [self._create_one_online_transaction(
                    transaction_identifier='ABCD02_pending',
                    date='2023-07-25', foreign_currency_code='GBP', amount_currency=8.0
                )],
            },
        ]
        start_date = fields.Date.from_string('2023-07-01')
        wizard = self.env['account.missing.transaction.wizard'].new({
            'date': start_date,
            'journal_id': self.euro_bank_journal.id,
        })

        action = wizard.action_fetch_missing_transaction()
        transient_transactions = self.env['account.bank.statement.line.transient'].search(domain=action['domain'])
        egp_currency = self.env['res.currency'].search([('name', '=', 'EGP')])
        gbp_currency = self.env['res.currency'].search([('name', '=', 'GBP')])

        self.assertEqual(2, len(transient_transactions))
        # Posted Transaction
        self.assertEqual(transient_transactions[0]['online_transaction_identifier'], 'ABCD01')
        self.assertEqual(transient_transactions[0]['date'], fields.Date.from_string('2023-07-06'))
        self.assertEqual(transient_transactions[0]['state'], 'posted')
        self.assertEqual(transient_transactions[0]['foreign_currency_id'], egp_currency)
        self.assertEqual(transient_transactions[0]['amount_currency'], 8.0)
        # Pending Transaction
        self.assertEqual(transient_transactions[1]['online_transaction_identifier'], 'ABCD02_pending')
        self.assertEqual(transient_transactions[1]['date'], fields.Date.from_string('2023-07-25'))
        self.assertEqual(transient_transactions[1]['state'], 'pending')
        self.assertEqual(transient_transactions[1]['foreign_currency_id'], gbp_currency)
        self.assertEqual(transient_transactions[1]['amount_currency'], 8.0)

    def test_missing_transaction_transient_handle_dict_properly_for_transaction_details(self):
        expected_transaction_details = {
            'online_transaction_identifier': 'ABCD01',
            'date': '2023-07-06',
            'payment_ref': 'ABCD01',
            'amount': 10.0,
            'partner_name': 'Test partner',
        }

        transaction_to_import = {
            **self._create_one_online_transaction(
                transaction_identifier='ABCD01',
                date='2023-07-06',
                payment_ref='ABCD01',
                amount=10.0,
                partner_name='Test partner',
                transaction_details=True,
            ),
            'journal_id': self.euro_bank_journal.id,
            'company_id': self.euro_bank_journal.company_id.id,
        }
        transient_transaction = self.env['account.bank.statement.line.transient'].create(transaction_to_import)

        transaction_details = transient_transaction.read(['transaction_details'], load=None)[0]['transaction_details']
        self.assertEqual(transaction_details, expected_transaction_details)

        transient_transaction.action_import_transactions()

        transaction = self.env['account.bank.statement.line'].search([('payment_ref', '=', 'ABCD01')], limit=1)
        self.assertEqual(transaction.transaction_details, expected_transaction_details)

    @patch('odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._fetch_odoo_fin')
    def test_fetch_missing_transaction_with_end_to_end_uuid(self, patched_fetch_odoofin):
        """Tests that the wizard works when the end-to-end uuid is sent from OdooFin."""
        self.account_online_link.state = 'connected'
        patched_fetch_odoofin.side_effect = [
            {
                'transactions': [self._create_one_online_transaction(
                    transaction_identifier='ABCD01',
                    date='2023-07-06',
                    end_to_end_uuid='123',
                )],
            },
            {
                'transactions': [self._create_one_online_transaction(
                    transaction_identifier='ABCD02_pending',
                    date='2023-07-25',
                    end_to_end_uuid='123',
                )],
            },
        ]

        wizard = self.env['account.missing.transaction.wizard'].new({
            'date': '2023-07-01',
            'journal_id': self.euro_bank_journal.id,
        })

        action = wizard.action_fetch_missing_transaction()
        transient_transactions = self.env['account.bank.statement.line.transient'].search(domain=action['domain'])
        self.assertEqual(2, len(transient_transactions))

    @patch('odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._fetch_odoo_fin')
    def test_fetch_pending_transaction_with_end_to_end_uuid(self, patched_fetch_odoofin):
        """Tests that the pending transactions works when the end-to-end uuid is sent from OdooFin."""
        self.account_online_link.state = 'connected'
        patched_fetch_odoofin.side_effect = [
            {
                'transactions': [self._create_one_online_transaction(
                    transaction_identifier='ABCD01',
                    date='2023-07-06',
                    end_to_end_uuid='123',
                )],
            },
            {
                'transactions': [self._create_one_online_transaction(
                    transaction_identifier='ABCD02_pending',
                    date='2023-07-25',
                    end_to_end_uuid='123',
                )],
            },
        ]

        action = self.euro_bank_journal.action_open_pending_bank_statement_lines()
        transient_transactions = self.env['account.bank.statement.line.transient'].search(domain=action['domain'])
        self.assertEqual(1, len(transient_transactions))
