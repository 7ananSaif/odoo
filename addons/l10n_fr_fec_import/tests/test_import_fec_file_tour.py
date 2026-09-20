import datetime

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingHttpCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestImportFecFileTour(AccountTestInvoicingHttpCommon):
    def test_import_fec_file(self):
        """
        Test the correct importation of the following models:
        1. Accounts
        2. Journals
        3. Partners
        4. Moves
        5. Move lines
        """
        self.start_tour('/odoo', 'import_fec_file_tour', login=self.env.user.login)

        with self.subTest(test='Test imported accounts'):
            account_codes = ('401000', '445660', '622700')
            domain = [('company_ids', '=', self.company.id), ('code', 'in', account_codes)]
            accounts = self.env['account.account'].with_company(self.company.id).search(domain, order='code')

            expected_values = [{
                'name': 'Suppliers',
                'account_type': 'liability_payable',
                'reconcile': True
            }, {
                'name': 'ASSURANCE',
                'account_type': 'asset_current',
                'reconcile': False,
            }, {
                'name': 'Legal costs and litigation',
                'account_type': 'expense',
                'reconcile': False,
            }]
            self.assertRecordValues(accounts, expected_values)

        with self.subTest(test='Test imported journals'):
            journal_codes = ('ACH', )
            domain = [('company_id', '=', self.company.id), ('code', 'in', journal_codes)]
            journals = self.env['account.journal'].search(domain, order='code')

            expected_values = [{'name': 'FEC-ACHATS', 'type': 'general'}]
            self.assertRecordValues(journals, expected_values)

        with self.subTest(test='Test imported partners'):
            partner_refs = ('PARTNER01', )
            domain = [('company_id', '=', self.company.id), ('ref', 'in', partner_refs)]
            partners = self.env['res.partner'].search(domain, order='ref')

            expected_values = [{'name': 'PARTNER 01'}]
            self.assertRecordValues(partners, expected_values)

        with self.subTest(test='Test imported moves'):
            move_names = ('ACH000001', 'ACH000002', 'ACH000003')
            domain = [('company_id', '=', self.company.id), ('name', 'in', move_names)]
            moves = self.env['account.move'].search(domain, order='name')

            journal = self.env['account.journal'].with_context(active_test=False).search([('code', '=', 'ACH')])
            expected_values = [{
                'name': move_names[0],
                'journal_id': journal.id,
                'date': datetime.date(2018, 8, 8),
                'move_type': 'entry',
                'ref': '1'
            }, {
                'name': move_names[1],
                'journal_id': journal.id,
                'date': datetime.date(2018, 8, 8),
                'move_type': 'entry',
                'ref': '2'
            }, {
                'name': move_names[2],
                'journal_id': journal.id,
                'date': datetime.date(2018, 9, 10),
                'move_type': 'entry',
                'ref': '3'
            }]
            self.assertRecordValues(moves, expected_values)

            self.assertEqual(1, len(moves[2].line_ids.filtered(lambda x: x.partner_id.name == 'PARTNER 01')))

        with self.subTest(test='Test imported move lines'):
            move_names = ('ACH000001', 'ACH000002', 'ACH000003', 'ACH000006')
            domain = [('company_id', '=', self.company.id), ('move_name', 'in', move_names)]
            move_lines = self.env['account.move.line'].search(domain, order='move_name, id')
            columns = ['name', 'credit', 'debit']
            lines = [
                ('ADVANCE PAYMENT COMPANY FORMALITIES', 0.00, 500.00),
                ('ADVANCE PAYMENT COMPANY FORMALITIES', 0.00, 100.00),
                ('ADVANCE PAYMENT COMPANY FORMALITIES', 600.00, 0.00),
                ('DOMICILIATION', 0.00, 300.00),
                ('DOMICILIATION', 0.00, 60.00),
                ('DOMICILIATION', 360.00, 0.00),
                ('PARTNER 01', 0.00, 41.50),
                ('PARTNER 01', 0.00, 8.30),
                ('PARTNER 01', 49.80, 0.00),
                ('ASSURANCE', 0.00, 200.50),
                ('ASSURANCE', 200.50, 0.00),
            ]
            expected_values = [dict(zip(columns, line)) for line in lines]
            self.assertRecordValues(move_lines, expected_values)
