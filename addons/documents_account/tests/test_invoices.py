# -*- coding: utf-8 -*-
import base64

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.documents_account.tests.common import DocumentsAccountHelpersCommon, PDF
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestInvoices(AccountTestInvoicingCommon, DocumentsAccountHelpersCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids += cls.quick_ref('documents.group_documents_manager')
        cls.test_partner = cls.env['res.partner'].create({'name': 'test Azure'})
        cls.document = cls.env['documents.document'].create({
            'datas': base64.b64encode(b"test_suspense_statement_line_id"),
            'name': 'file.txt',
            'mimetype': 'text/plain',
            'partner_id': cls.test_partner.id,
        })
        cls.folder_test = cls.env['documents.document'].create({'name': 'Test Bills', 'type': 'folder'})
        cls.invoice = cls.init_invoice("in_invoice", amounts=[1000], post=True)

    def test_suspense_statement_line_id(self):
        # Remove all autoconfigured journal synchronization settings for documents
        self.env['documents.account.folder.setting'].search([]).unlink()

        reconcile_activity_type = self.env['mail.activity.type'].create({
            "name": "Reconciliation request",
            "category": "upload_file",
            "folder_id": self.env.ref("documents.document_finance_folder").id,
            "res_model": "account.move",
        })

        st = self.env['account.bank.statement'].create({
            'line_ids': [Command.create({
                'amount': -1000.0,
                'date': '2017-01-01',
                'journal_id': self.company_data['default_journal_bank'].id,
                'payment_ref': 'test_suspense_statement_line_id',
            })],
        })
        st.balance_end_real = st.balance_end
        st_line = st.line_ids
        move = st_line.move_id

        # Log an activity on the move using the "Reconciliation Request".
        activity = self.env['mail.activity'].create({
            'activity_type_id': reconcile_activity_type.id,
            'note': "test_suspense_statement_line_id",
            'res_id': move.id,
            'res_model_id': self.env.ref('account.model_account_move').id,
        })
        activity._onchange_activity_type_id()

        # A new document has been created.
        documents = self.env['documents.document'].search([('request_activity_id', '=', activity.id)])
        self.assertTrue(documents.exists())

        # Upload an attachment.
        attachment = self.env['ir.attachment'].create({
            'name': "test_suspense_statement_line_id",
            'datas': base64.b64encode(b"test_suspense_statement_line_id"),
            'res_model': move._name,
            'res_id': move.id,
        })
        activity._action_done(attachment_ids=attachment.ids)

        # Upload as a vendor bill.
        vendor_bill_action = documents.account_create_account_move('in_invoice')
        self.assertTrue(vendor_bill_action.get('res_id'))
        vendor_bill = self.env['account.move'].browse(vendor_bill_action['res_id'])

        self.assertRecordValues(vendor_bill, [{'suspense_statement_line_id': st_line.id}])

        self.setup_sync_journal_folder(self.invoice.journal_id, self.folder_test)

        action = self.document.account_create_account_move('in_invoice')
        self.assertEqual(self.document.partner_id, self.test_partner)
        self.assertEqual(self.env['account.move'].browse([action['res_id']]).partner_id, self.test_partner,
                         "Document partner must be set on the created account move")

    def test_create_account_move_on_archived_document(self):
        """Check that when creating an account move on an archived document, it updates and unarchives it."""
        self.setup_sync_journal_folder(self.invoice.journal_id, self.folder_test)
        self.document.action_archive()
        self.assertFalse(self.document.folder_id)
        self.document.account_create_account_move('in_invoice')
        self.assertEqual(self.document.folder_id, self.folder_test)
        self.assertTrue(self.document.active)

    def test_vendor_bill_defaults_to_supplier_currency(self):
        if 'property_purchase_currency_id' not in self.env['res.partner']:
            self.skipTest('Purchase module not installed, skipping supplier currency test.')

        eur = self._enable_currency('EUR')
        usd = self._enable_currency('USD')
        new_company = self.setup_other_company(name='New Company', currency_id=eur.id)['company']
        self.env.user.company_id = new_company
        supplier = self.env['res.partner'].create({
            'name': 'Supplier USD',
            'property_purchase_currency_id': usd.id,
        })
        folder = self.env['documents.document'].create({
            'name': 'Test Folder',
            'type': 'folder',
        })
        document = self.env['documents.document'].create({
            'name': 'bill.pdf',
            'mimetype': 'application/pdf',
            'folder_id': folder.id,
            'partner_id': supplier.id,
            'datas': PDF,
        })
        action = document.account_create_account_move('in_invoice')
        self.assertTrue(action.get('res_id'), "Vendor bill should be created")
        bill = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(
            bill.currency_id.id,
            usd.id,
            "Vendor bill currency should match supplier's purchase currency"
        )
