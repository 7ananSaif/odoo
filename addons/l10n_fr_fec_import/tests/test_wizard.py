# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
import json
import logging

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo import Command, tools

_logger = logging.getLogger(__name__)


@tagged('post_install_l10n', 'post_install', '-at_install')
class AccountTestFecImport(AccountTestInvoicingCommon):
    """ Main test class for Account FEC import testing """

    # ----------------------------------------
    # 1:: Test class body
    # ----------------------------------------

    @classmethod
    @AccountTestInvoicingCommon.setup_country('fr')
    def setUpClass(cls):
        super().setUpClass()

        # Export company
        cls.company_data_2 = cls.setup_other_company(vat='FR15437982937')
        cls.company_export = cls.company_data_2['company']

        # Export records
        cls.env['account.move'].with_company(cls.company_export).create([
            {
                'name': 'INV/001/123456',
                'date': datetime.date(2010, 1, 1),
                'invoice_date': datetime.date(2010, 1, 1),
                'move_type': 'entry',
                'partner_id': cls.partner_a.id,
                'journal_id': cls.company_data_2['default_journal_sale'].id,
                'line_ids': [
                    Command.create({
                        'name': 'line-1',
                        'account_id': cls.company_data_2['default_account_receivable'].id,
                        'credit': 0.0,
                        'debit': 100.30,
                    }),
                    Command.create({
                        'name': 'line-2',
                        'account_id': cls.company_data_2['default_account_tax_sale'].id,
                        'credit': 100.30,
                        'debit': 0.0,
                    }),
                ],
            }, {
                'name': 'INV/001/123457',
                'move_type': 'entry',
                'date': datetime.date(2010, 1, 1),
                'invoice_date': datetime.date(2010, 1, 1),
                'partner_id': cls.partner_b.id,
                'journal_id': cls.company_data_2['default_journal_purchase'].id,
                'line_ids': [
                    Command.create({
                        'name': 'line-3',
                        'account_id': cls.company_data_2['default_account_payable'].id,
                        'credit': 65.15,
                        'debit': 0.0,
                    }),
                    Command.create({
                        'name': 'line-4',
                        'account_id': cls.company_data_2['default_account_expense'].id,
                        'credit': 0.0,
                        'debit': 65.15,
                    }),
                ],
            },
        ])

    def _import_fec_file(self, file_name, company=None, **kwargs):
        company = company or self.env.company
        wizard = self.env['account.fec.import.wizard'].with_company(company).create({**kwargs})
        with tools.file_open(f'l10n_fr_fec_import/static/tests/fec_test_files/{file_name}', mode='rb') as raw_file:
            decoded_file = raw_file.read().decode()
            json_content = json.loads(decoded_file)
            header = json_content['header']
            chunks = json_content['chunks']
            for chunk in chunks:
                wizard.process_chunk(header, chunk)
        return wizard

    # ----------------------------------------
    # 2:: Test methods
    # ----------------------------------------
    def test_fec_import_ignores_empty_partner_refs(self):
        """ Ensure that FEC import does not assign a partner when no reference is provided. """
        self.env['res.partner'].create({'name': 'Partner A', 'ref': '', 'company_id': self.company.id})

        self._import_fec_file('fec_lf_tab_utf8.json')
        move = self.env['account.move'].search([('company_id', '=', self.company.id), ('name', '=', 'ACH000001')])
        self.assertFalse(move.mapped('line_ids.partner_id'))
        self.assertFalse(move.partner_id)

    def test_import_fec_partners_no_duplicate(self):
        """
        Test that the partners are not imported from the FEC file if already existing
        But that if two partners have the same name but a different ref, they are correctly created and linked
        """
        partner_1 = self.env['res.partner'].create({
            'name': 'PARTNER 01',
            'ref': 'PARTNER01'
        })

        self._import_fec_file('fec_lf_tab_utf8.json')

        partners_1 = self.env['res.partner'].search_count([('ref', '=', partner_1.ref)])
        self.assertEqual(partners_1, 1)

        partners_2 = self.env['res.partner'].search([('ref', '=', 'PARTNER02')])
        self.assertEqual(len(partners_2), 1)

        domain = [('company_id', '=', self.company.id), ('move_name', '=', 'ACH000007')]
        move_lines = self.env['account.move.line'].search(domain, order='move_name, id')
        self.assertEqual(move_lines.partner_id, partners_2)

    def test_import_fec_big_file(self):
        """ Test that FEC import works fine with larger files """

        last = self.env['account.move'].search([], order='id desc', limit=1)
        self._import_fec_file('fec_crlf_tab_utf8bom_large.json')

        new = self.env['account.move'].search([('id', '>', last.id)])
        # We delay one move to be sure the FEC matching number is not lost
        # when performing the first posting/auto matching
        delayed_move = self.env['account.move.line'].search([('matching_number', '=', 'IAA')], limit=1).move_id

        (new - delayed_move).action_post()
        delayed_move.action_post()

        # Verify move_lines presence
        move_names = ('ACH000001', 'ACH000002', 'ACH000003')
        domain = [('company_id', '=', self.company.id), ('move_name', 'in', move_names)]
        move_lines = self.env['account.move.line'].search(domain, order='move_name, id')
        self.assertEqual(9, len(move_lines))

        # Verify Reconciliation
        domain = [('company_id', '=', self.company.id), ('reconciled', '=', True)]
        move_lines = self.env['account.move.line'].search(domain)
        self.assertEqual(256, len(move_lines))

        # Verify Full Reconciliation
        domain = [('company_id', '=', self.company.id), ('full_reconcile_id', '!=', False)]
        move_lines = self.env['account.move.line'].search(domain)
        self.assertEqual(256, len(move_lines))

        # Verify Journal types
        domain = [('company_id', '=', self.company.id), ('name', '=', 'FEC-BQ 552')]
        journal = self.env['account.journal'].search(domain)
        self.assertEqual(journal.type, 'bank')

    def test_import_fec_export(self):
        """ Test that imports the results of a FEC export """

        # Export Wizard ----------------------------------------
        export_wizard = self.env['l10n_fr.fec.export.wizard'].with_company(self.company_export).create([{
            'date_from': datetime.date(1990, 1, 1),
            'date_to': datetime.date.today(),
            'test_file': True,
            'export_type': 'nonofficial'
        }])

        # Generate the FEC content with the export wizard
        def split_fields(csv_content):
            lines = csv_content.split('\r\n')
            fields = [line.split('|') for line in lines]
            # We remove the 'CompAuxNum' @6 because we use partner.id in it
            # and we don't care about comparing partner.id
            fields[1:] = [[*field[:6], '', *field[7:]] for field in fields[1:]]
            return fields
        exported_content = split_fields(export_wizard.generate_fec()['file_content'].decode())
        with tools.file_open('l10n_fr_fec_import/static/tests/fec_test_files/fec_crlf_pipe_utf8_export.txt', mode='rb') as raw_file:
            expected_export = split_fields(raw_file.read().decode())
            self.assertEqual(exported_content, expected_export)

        # Importing the fec file
        self._import_fec_file('fec_crlf_pipe_utf8_export.json')

        # Verify moves data
        new_moves = self.env['account.move'].search([
            ('company_id', '=', self.company_export.id),
            ('closing_return_id', '=', False),  # exclude automatic tax closing  entries
        ], order="name")
        columns = ['company_id', 'name', 'journal_id', 'partner_id', 'date']
        moves_data = [
            (self.company_export.id, 'INV/001/123456', self.company_data_2['default_journal_sale'].id, self.partner_a.id, datetime.date(2010, 1, 1)),
            (self.company_export.id, 'INV/001/123457', self.company_data_2['default_journal_purchase'].id, self.partner_b.id, datetime.date(2010, 1, 1)),
        ]
        expected_values = [dict(zip(columns, move_data)) for move_data in moves_data]
        self.assertRecordValues(new_moves, expected_values)

        # Verify moves lines data
        columns = ['company_id', 'name', 'credit', 'debit', 'account_id']
        lines_data = [
            (self.company_export.id, 'line-1', 0.00, 100.30, self.company_data_2['default_account_receivable'].id),
            (self.company_export.id, 'line-2', 100.30, 0.00, self.company_data_2['default_account_tax_sale'].id),
            (self.company_export.id, 'line-3', 65.15, 0.00, self.company_data_2['default_account_payable'].id),
            (self.company_export.id, 'line-4', 0.00, 65.15, self.company_data_2['default_account_expense'].id),
        ]
        expected_values = [dict(zip(columns, line_data)) for line_data in lines_data]
        new_lines = new_moves.mapped("line_ids").sorted(key=lambda x: x.name)
        self.assertRecordValues(new_lines, expected_values)

    def test_balance_moves_by_day(self):
        """ Test that the imbalanced moves are correctly balanced with a grouping by day """

        self._import_fec_file('fec_cr_tab_utf8_imbalanced_day.json')

        domain = [('company_id', '=', self.company.id), ('move_name', 'in', ('ACH/20180808', 'ACH/20180910'))]
        move_lines = self.env['account.move.line'].search(domain, order='move_name,name')

        self.assertEqual(
            move_lines.mapped(lambda line: (line.move_name, line.name)),
            [
                ('ACH/20180808', 'ADVANCE PAYMENT COMPANY FORMALITIES'),
                ('ACH/20180808', 'ADVANCE PAYMENT COMPANY FORMALITIES'),
                ('ACH/20180808', 'ADVANCE PAYMENT COMPANY FORMALITIES'),
                ('ACH/20180808', 'DOMICILIATION'),
                ('ACH/20180808', 'DOMICILIATION'),
                ('ACH/20180808', 'DOMICILIATION'),
                ('ACH/20180910', 'ASSURANCE'),
                ('ACH/20180910', 'ASSURANCE'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
            ])

    def test_balance_moves_by_month(self):
        """ Test that the imbalanced moves are correctly balanced with a grouping by month """

        self._import_fec_file('fec_lf_tab_utf8_imbalanced_month.json')

        domain = [('company_id', '=', self.company.id), ('move_name', 'in', ('ACH/201808', 'ACH/20180910'))]
        move_lines = self.env['account.move.line'].search(domain, order='move_name,name')
        self.assertEqual(
            move_lines.mapped(lambda line: (line.move_name, line.name)),
            [
                ('ACH/201808', 'ADVANCE PAYMENT COMPANY FORMALITIES'),
                ('ACH/201808', 'ADVANCE PAYMENT COMPANY FORMALITIES'),
                ('ACH/201808', 'ADVANCE PAYMENT COMPANY FORMALITIES'),
                ('ACH/201808', 'DOMICILIATION'),
                ('ACH/201808', 'DOMICILIATION'),
                ('ACH/201808', 'DOMICILIATION'),
                ('ACH/20180910', 'ASSURANCE'),
                ('ACH/20180910', 'ASSURANCE'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
                ('ACH/20180910', 'PARTNER 01'),
            ])

    def test_unbalanceable_moves(self):
        """ Test that the imbalanced moves raise as they cannot be balanced by day/month """
        with self.assertRaises(UserError):
            self._import_fec_file('fec_lf_tab_utf8_imbalanced.json')

    def test_positive_montant_devise(self):
        """
        Test that it doesn't fail even when the MontantDevise is not signed, i.e. MontantDevise is positive even
        when the line is credited, or the opposite case: MontantDevise is negative while the line is
        debited.
        """
        self._import_fec_file('fec_cr_tab_utf8bom.json')

    def test_fec_import_multicompany(self):
        self._import_fec_file('fec_lf_tab_utf8.json')
        fr_company2 = self.setup_other_company(name="Company FR 2")['company']
        self._import_fec_file('fec_lf_tab_utf8.json', company=fr_company2)

    def test_fec_import_reconciliation(self):
        last = self.env['account.move'].search([], order='id desc', limit=1)
        self._import_fec_file('fec_crlf_tab_utf8.json')
        new = self.env['account.move'].search([('id', '>', last.id)])
        self.assertEqual(len(new), 4)
        self.assertFalse(new.line_ids.full_reconcile_id, "Reconciliation is only temporary before posting")
        new.action_post()
        self.assertEqual(len(new.line_ids.full_reconcile_id), 2, "It is fully reconciled after posting")

    def test_key_is_empty(self):
        with self.assertRaisesRegex(UserError, "journal not found"):
            self._import_fec_file('fec_lf_tab_utf8-2.json')

    def test_no_update_journal(self):
        """Test that existing journal type is not updated when importing FEC file."""
        self._import_fec_file('fec_lf_tab_utf8.json')
        purchase_journal = self.env['account.journal'].search([('code', '=', 'ACH')])
        self.assertEqual(purchase_journal.type, 'general')
        purchase_journal.type = 'purchase'
        self._import_fec_file('fec_lf_tab_utf8.json')
        self.assertEqual(purchase_journal.type, 'purchase')

    def test_created_account_translation(self):
        self.env['res.lang']._activate_lang('fr_FR')
        self.env['account.account'].search([('name', '=', 'Subscribed capital - uncalled')]).unlink()
        self._import_fec_file('fec_lf_pipe_iso.json')
        account = self.env['account.account'].search([('name', '=', 'Capital')]).with_context(lang="fr_FR")
        self.assertEqual(account.name, 'Capital souscrit - non appelé')

    def test_currency_rounding_with_decimal_values(self):
        """
        Test that it doesn't fail even when the currency has a rounding of 1, and the lines include values with decimal points.
        """
        self.env["res.currency"].create({"name": "xxx", "symbol": "X", "rounding": 1})
        self._import_fec_file('fec_lf_tab_utf8-3.json')

    def test_import_wizard_fields(self):
        last = self.env['account.move.line'].search([], order='id desc', limit=1)
        import_summary = self._import_fec_file('fec_lf_tab_utf8.json').import_summary_id
        self.assertEqual(import_summary.import_summary_have_data, True)
        self.assertNotEqual(last, self.env['account.move.line'].search([], order='id desc', limit=1))

        last = self.env['account.move.line'].search([], order='id desc', limit=1)
        import_summary = self._import_fec_file('fec_lf_tab_utf8.json', duplicate_documents_handling='ignore').import_summary_id
        self.assertEqual(import_summary.import_summary_have_data, False)
        self.assertEqual(last, self.env['account.move.line'].search([], order='id desc', limit=1))

        last = self.env['account.move.line'].search([], order='id desc', limit=1)
        import_summary = self._import_fec_file('fec_lf_tab_utf8.json').import_summary_id
        self.assertEqual(import_summary.import_summary_have_data, True)
        self.assertNotEqual(last, self.env['account.move.line'].search([], order='id desc', limit=1))

        last = self.env['account.move.line'].search([], order='id desc', limit=1)
        import_summary = self._import_fec_file('fec_lf_tab_utf8.json', duplicate_documents_handling='ignore', document_prefix='PRE').import_summary_id
        self.assertEqual(import_summary.import_summary_have_data, True)
        self.assertNotEqual(last, self.env['account.move.line'].search([], order='id desc', limit=1))

        last = self.env['account.move.line'].search([], order='id desc', limit=1)
        import_summary = self._import_fec_file('fec_lf_tab_utf8.json', duplicate_documents_handling='ignore', document_prefix='PRE').import_summary_id
        self.assertEqual(import_summary.import_summary_have_data, False)
        self.assertEqual(last, self.env['account.move.line'].search([], order='id desc', limit=1))

    def test_account_name(self):
        """
        Template should not override the account's name given by the user
        We defined
        ACH\tACHATS\tACH000001\t20180808\t45500000\tAssociate's current account\t\t\t1\t20180808\tADVANCE PAYMENT COMPANY FORMALITIES\t0,00\t600,00\t\t\t20190725\t\t
        We should retrieve the name "Associate's current account"
        """

        self._import_fec_file('fec_lf_tab_utf8_imbalanced_month.json')
        account = self.env['account.account'].search([('code', '=', '455000')])
        self.assertEqual(account.name, "Associate's current account")
