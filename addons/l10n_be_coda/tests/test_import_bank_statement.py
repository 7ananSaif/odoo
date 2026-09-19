# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (c) 2012 Noviat nv/sa (www.noviat.be). All rights reserved.
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged
from odoo.tools import file_open


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCodaFile(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()

        cls.bank_journal = cls.company_data['default_journal_bank']

        cls.coda_file = cls._get_coda_file('l10n_be_coda/test_coda_file/Ontvangen_CODA.2013-01-11-18.59.15.txt')
        cls.coda_globalisation_file = cls._get_coda_file('l10n_be_coda/test_coda_file/test_coda_globalisation.txt')

    @classmethod
    def _get_coda_file(cls, coda_file_path):
        with file_open(coda_file_path, 'rb') as coda_file:
            return coda_file.read()

    def test_coda_file_import(self):
        self.company_data['default_journal_bank'].create_document_from_attachment(self.env['ir.attachment'].create({
            'mimetype': 'application/text',
            'name': 'Ontvangen_CODA.2013-01-11-18.59.15.txt',
            'raw': self.coda_file,
        }).ids)

        imported_statement = self.env['account.bank.statement'].search([('company_id', '=', self.env.company.id)])
        self.assertRecordValues(imported_statement, [{
            'balance_start': 11812.70,
            'balance_end_real': 13646.05,
        }])

    def test_coda_file_import_twice(self):
        self.company_data['default_journal_bank'].create_document_from_attachment(self.env['ir.attachment'].create({
            'mimetype': 'application/text',
            'name': 'Ontvangen_CODA.2013-01-11-18.59.15.txt',
            'raw': self.coda_file,
        }).ids)

        with self.assertRaises(Exception):
            self.company_data['default_journal_bank'].create_document_from_attachment(self.env['ir.attachment'].create({
                'mimetype': 'application/text',
                'name': 'Ontvangen_CODA.2013-01-11-18.59.15.txt',
                'raw': self.coda_file,
            }).ids)

    def test_coda_special_chars(self):
        coda_special_chars = """0000001022372505        0123456789JOHN DOE                  KREDBEBB   00477472701 00000                                       2
12001BE68539007547034                  EUR0000000000100000310123DEMO COMPANY              KBC Business Account               027
2100010000ABCDEFG123456789000010000000000025500010223001500000Théâtre d'Hélène à Dümùß                             01022302701 0
2200010000                                                                                        GEBABEBB                   1 0
2300010000BE55173363943144                     ODOO SA                                                                       0 0
8027BE68539007547034                  EUR0000000000125500010223                                                                0
9               000005000000000000000000000000025500                                                                           2"""

        encodings = ('utf_8', 'cp850', 'cp858', 'cp1140', 'cp1252', 'iso8859_15', 'utf_32', 'utf_16', 'windows-1252')

        for enc in encodings:
            statements = self.company_data['default_journal_bank']._parse_bank_statement_file(coda_special_chars.encode(enc))[0][2]
            self.assertEqual(statements[0]['transactions'][0]['payment_ref'][:24], "Théâtre d'Hélène à Dümùß")


    def test_coda_zero_date(self):
        coda_zero_date = """0000001122472505        0123456789JOHN DOE                  KREDBEBB   00477472701 00000                                       2
12001BE68539007547034                  EUR0000000000100000310123DEMO COMPANY              KBC Business Account               027
2100010000ABCDEFG123456789000010000000000025500010223001500000Payment Reference                                    00000002701 0
2200010000                                                                                        GEBABEBB                   1 0
2300010000BE55173363943144                     ODOO SA                                                                       0 0
8027BE68539007547034                  EUR0000000000125500000000                                                                0
9               000005000000000000000000000000025500                                                                           2"""
        statements = self.company_data['default_journal_bank']._parse_bank_statement_file(coda_zero_date.encode('utf-8'))[0][2]
        self.assertEqual(statements[0]['transactions'][0]['date'], '2024-12-01')

    def test_coda_import_currency_symbol(self):
        coda_currency_symbols = """0000001122472505        0123456789JOHN DOE                  KREDBEBB   00477472701 00000                                       2
12001BE68539007547034                  EUR0000000000100000310123DEMO COMPANY              KBC Business Account               027
2100010000ABCDEFG123456789000010000000000025500010223001500000Payment Reference €$£¥¢                              00000002701 0
2200010000                                                                                        GEBABEBB                   1 0
2300010000BE55173363943144                     ODOO SA                                                                       0 0
8027BE68539007547034                  EUR0000000000125500000000                                                                0
9               000005000000000000000000000000025500                                                                           2"""
        statements = self.company_data['default_journal_bank']._parse_bank_statement_file(coda_currency_symbols.encode('utf-8'))[0][2]
        # If this fails, the error will probably talk about the date, it's because one of the decoded currency symbols became multiple
        # characters and the index of the date moved (from [115:121] to [117:123] for example)
        self.assertEqual(statements[0]['transactions'][0]['payment_ref'][:23], "Payment Reference €$£¥¢")

    def test_coda_multi_accounts(self):
        bank_1, bank_2 = self.env['res.partner.bank'].create([
            {'acc_number': 'BE33737018595246', 'partner_id': self.env.company.partner_id.id},
            {'acc_number': 'BE33737018595247', 'partner_id': self.env.company.partner_id.id},
        ])
        journal_1 = self.bank_journal
        journal_1.bank_account_id = bank_1
        journal_2 = journal_1.copy({'bank_account_id': bank_2.id})
        with file_open('l10n_be_coda/test_coda_file/multi_accounts.COD', 'rb') as coda_file:
            coda_file = coda_file.read()
        action = self.company_data['default_journal_bank'].create_document_from_attachment(self.env['ir.attachment'].create({
            'mimetype': 'application/text',
            'name': 'multi_accounts.COD',
            'raw': coda_file,
        }).ids)
        self.assertEqual(
            self.env['account.bank.statement.line'].search(action['domain'])['journal_id'],
            journal_1 + journal_2,
        )

    def test_coda_import_atm_pos_transaction_import_partner_from_struct_com(self):
        coda = """0000001122472505        0123456789JOHN DOE                  KREDBEBB   00477472701 00000                                       2                              2
12001BE68539007547034                  EUR0000000000100000310123DEMO COMPANY              KBC Business Account               027
2100020001DALZ15199 BKTBPFBECPG1000000000380500250325804021000                                                     25032506110 0
2100030000OL98R57W3GBKTOTBBEPOS10000000000062002503250040200011135127880000006588101902254978525032512037TOYOTA EVE25032506101 0
2200030000RE    EVERE     000000000000000000000000000   0000000                                                              1 0
2300030000                                                                        00000                                      0 0
8027BE68539007547034                  EUR0000000000125500000000                                                                0
9               000005000000000000000000000000025500                                                                           2"""
        statements = self.company_data['default_journal_bank']._parse_bank_statement_file(coda.encode('utf-8'))[0][2]
        self.assertEqual(statements[0]['transactions'][0]['partner_name'], "TOYOTA EVERE (EVERE)")

    def test_globalisation_split_transactions(self):
        self.company_data['default_journal_bank'].coda_split_transactions = True
        self.company_data['default_journal_bank'].create_document_from_attachment(self.env['ir.attachment'].create({
            'mimetype': 'application/text',
            'name': 'test_coda_globalisation.coda',
            'raw': self.coda_globalisation_file,
        }).ids)

        imported_statement = self.env['account.bank.statement'].search([('company_id', '=', self.env.company.id)])

        self.assertRecordValues(imported_statement.line_ids, [
            {'amount': -435.00},
            {'amount': 3044.45},
            {'amount': -419.92},
            {'amount': -59.12},
            {'amount': -419.92},
            {'amount': -59.12},
            {'amount': 63.74},
            {'amount': -1718.48},
            {'amount': -1077.21},
            {'amount': -8.00},
            {'amount': -1.68},
        ])

        self.assertRecordValues(imported_statement, [{
            'balance_start': 11812.70,
            'balance_end': 10722.44,
            'balance_end_real': 10722.44,
        }])

    def test_globalisation_no_split_transactions(self):
        self.company_data['default_journal_bank'].coda_split_transactions = False
        self.company_data['default_journal_bank'].create_document_from_attachment(self.env['ir.attachment'].create({
            'mimetype': 'application/text',
            'name': 'test_coda_globalisation.coda',
            'raw': self.coda_globalisation_file,
        }).ids)

        imported_statement = self.env['account.bank.statement'].search([('company_id', '=', self.env.company.id)])

        self.assertRecordValues(imported_statement.line_ids, [
            {'amount': -435.00},
            {'amount': 3044.45},
            {'amount': -479.04},
            {'amount': -479.04},
            {'amount': 63.74},
            {'amount': -2795.69},
            {'amount': -9.68},
        ])

        self.assertRecordValues(imported_statement, [{
            'balance_start': 11812.70,
            'balance_end': 10722.44,
            'balance_end_real': 10722.44,
        }])
