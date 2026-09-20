import base64
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import file_open
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCodabox(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()

        bank_1, bank_2 = cls.env['res.partner.bank'].create([
            {'acc_number': 'BE33737018595246', 'partner_id': cls.env.company.partner_id.id},
            {'acc_number': 'BE33737018595247', 'partner_id': cls.env.company.partner_id.id},
        ])
        cls.bank_journal_1 = cls.company_data['default_journal_bank']
        cls.bank_journal_1.bank_account_id = bank_1
        cls.bank_journal_2 = cls.bank_journal_1.copy({'bank_account_id': bank_2.id})
        with file_open('l10n_be_coda/test_coda_file/Ontvangen_CODA.2013-01-11-18.59.15.txt', 'rb') as coda_file:
            cls.coda_file = base64.b64encode(coda_file.read())
        with file_open('l10n_be_coda/test_coda_file/multi_accounts.COD', 'rb') as coda_file:
            cls.coda_file_multi_accounts = base64.b64encode(coda_file.read())

    @patch('odoo.addons.l10n_be_codabox.models.account_journal.AccountJournal._l10n_be_codabox_fetch_transactions_from_iap')
    def test_codabox_file_import(self, patched_l10n_be_codabox_fetch_transactions_from_iap):
        patched_l10n_be_codabox_fetch_transactions_from_iap.return_value = [(self.coda_file, b'')]
        self.env.company.l10n_be_codabox_is_connected = True
        self.env['account.journal']._l10n_be_codabox_fetch_coda_transactions(self.env.company)
        imported_statement = self.env['account.bank.statement'].search([('company_id', '=', self.env.company.id)])
        self.assertRecordValues(imported_statement, [{
            'balance_start': 11812.70,
            'balance_end_real': 13646.05,
        }])

    @patch('odoo.addons.l10n_be_codabox.models.account_journal.AccountJournal._l10n_be_codabox_fetch_transactions_from_iap')
    def test_codabox_multi_accounts(self, patched_l10n_be_codabox_fetch_transactions_from_iap):
        patched_l10n_be_codabox_fetch_transactions_from_iap.return_value = [(self.coda_file_multi_accounts, b'')]
        self.env.company.l10n_be_codabox_is_connected = True
        self.env['account.journal']._l10n_be_codabox_fetch_coda_transactions(self.env.company)
        imported_statement = self.env['account.bank.statement'].search([('company_id', '=', self.env.company.id)])
        self.assertEqual(
            imported_statement.journal_id,
            self.bank_journal_1 + self.bank_journal_2,
        )
