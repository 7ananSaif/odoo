from itertools import product
from unittest.mock import patch

from odoo.addons.documents_account.tests.common import DocumentsAccountTestCommon
from odoo.exceptions import ValidationError
from odoo.tests import RecordCapturer
from odoo.tests.common import tagged


@tagged('post_install', '-at_install', 'test_document_bridge')
class TestIrActionsServer(DocumentsAccountTestCommon):

    def test_documents_account_record_create(self):
        """Test documents_account_record_create action server type (state)."""
        for move_type, with_journal in product(
                ('in_invoice', 'out_invoice', 'in_refund', 'out_refund', 'entry', 'in_receipt'),
                (False, True)):
            with (self.subTest(move_type=move_type, with_journal=with_journal),
                  RecordCapturer(self.env['account.move'], []) as capture):
                journal_id = self.env['account.move']._get_suitable_journal_ids(move_type)[:1]
                document = self.document_pdf.copy()
                action = self.env['ir.actions.server'].create({
                    'name': f'test {move_type}',
                    'model_id': self.env['ir.model']._get_id('documents.document'),
                    'state': 'documents_account_record_create',
                    'documents_account_create_model': f'account.move.{move_type}',
                    'documents_account_journal_id': journal_id.id if with_journal else False,
                })
                action.with_context({'active_model': 'documents.document', 'active_id': document.id}).run()
                account_move = capture.records
                self.assertEqual(len(account_move), 1)
                self.assertEqual(account_move.move_type, move_type)
                self.assertEqual(document.res_model, account_move._name)
                self.assertEqual(document.res_id, account_move.id)
                self.assertEqual(account_move.journal_id, journal_id)

        journal_id = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
        for with_journal in (False, True):
            with (self.subTest(with_journal=with_journal),
                  patch.object(self.env.registry["documents.document"],
                               'account_create_account_bank_statement', autospec=True) as mock):
                action = self.env['ir.actions.server'].create({
                    'name': 'account.bank.statement',
                    'model_id': self.env['ir.model']._get_id('documents.document'),
                    'state': 'documents_account_record_create',
                    'documents_account_create_model': 'account.bank.statement',
                    'documents_account_journal_id': journal_id.id if with_journal else False,
                })
                document = self.document_pdf.copy()
                action.with_context({'active_model': 'documents.document', 'active_id': document.id}).run()
                mock.assert_called()
                called_args, called_kwargs = mock.call_args
                self.assertEqual(called_args, (document, ))
                self.assertEqual(called_kwargs, {'journal_id': journal_id if with_journal else None})

    def test_documents_account_record_create_on_invalid_model(self):
        """Test that calling a documents_account_record_create action on a non-document record does nothing."""
        partner = self.env['res.partner'].create({'name': 'test'})
        with patch.object(self.env.registry["documents.document"], 'account_create_account_bank_statement') as mock:
            action = self.env['ir.actions.server'].create({
                'name': 'account.bank.statement',
                'model_id': self.env['ir.model']._get_id('documents.document'),
                'state': 'documents_account_record_create',
                'documents_account_create_model': 'account.bank.statement',
            })
            action.with_context({'active_model': 'res.partner', 'active_id': partner.id}).run()
            mock.assert_not_called()

    def test_documents_account_record_create_documents_only(self):
        """Test model enforcement on documents_account_record_create server action (can only be applied on Document)."""
        with self.assertRaises(ValidationError, msg='"New Journal Entry" can only be applied to Document.'):
            self.env['ir.actions.server'].create({
                'name': 'Wrong model',
                'model_id': self.env['ir.model']._get_id('res.partner'),
                'state': 'documents_account_record_create',
                'documents_account_create_model': 'account.move.in_invoice',
            })
