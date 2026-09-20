from freezegun import freeze_time
from io import BytesIO
from zipfile import ZipFile

from odoo.tests.common import HttpCase, tagged
from .common import TestMxEdiCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCFDIDownload(TestMxEdiCommon, HttpCase):

    @freeze_time('2017-01-01')
    def test_cfdi_download(self):
        invoice_1 = self._create_invoice()
        invoice_2 = self._create_invoice()
        invoice_3 = self._create_invoice()
        invoices = invoice_1 + invoice_2 + invoice_3
        with self.with_mocked_pac_sign_success():
            invoice_2._l10n_mx_edi_cfdi_invoice_try_send()
            invoice_3._l10n_mx_edi_cfdi_invoice_try_send()
        self.assertTrue(invoice_2.l10n_mx_edi_cfdi_attachment_id)
        self.assertTrue(invoice_3.l10n_mx_edi_cfdi_attachment_id)
        action_download = invoices.action_invoice_download_cfdi()
        self.assertEqual(
            action_download['url'],
            f'/account/download_invoice_documents/{invoice_2.id},{invoice_3.id}/cfdi',
            'Only invoices with a CFDI should be called in the URL',
        )
        res_1 = self.url_open(action_download['url'])
        self.assertEqual(res_1.status_code, 200)
        self.assertIn(
            'oe_login_form',
            res_1.content.decode('utf-8'),
            'When not authenticated, the download is not possible.'
        )
        self.authenticate(self.env.user.login, self.env.user.login)
        res_2 = self.url_open(action_download['url'])
        self.assertEqual(res_2.status_code, 200)
        with ZipFile(BytesIO(res_2.content)) as zip_file:
            self.assertEqual(
                zip_file.namelist(),
                (invoice_2 | invoice_3).l10n_mx_edi_cfdi_attachment_id.mapped('name'),
            )

    @freeze_time('2017-01-01')
    def test_payment_download(self):
        invoice = self._create_invoice()
        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()

        payment = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create([{
                'payment_date': '2017-06-01',
                'amount': 1160.0,
            }])\
            ._create_payments()

        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
            payment.l10n_mx_edi_payment_document_ids.action_force_payment_cfdi()

        action_download = payment.l10n_mx_edi_payment_document_ids[0].action_download_file()
        self.authenticate(self.env.user.login, self.env.user.login)
        res = self.url_open(action_download['url'])

        self.assertEqual(res.status_code, 200)

    @freeze_time('2017-01-01')
    def test_bank_transaction_download(self):
        invoice = self._create_invoice()
        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()

        bank_statement = self.env['account.bank.statement.line'].create([{
            'journal_id': self.company_data['default_journal_bank'].id,
            'payment_ref': 'payment_move_line',
            'partner_id': invoice.partner_id.id,
            'amount': 1160,
            'date': '2017-01-01',
        }])

        bank_statement.set_line_bank_statement_line(invoice.line_ids.filtered(lambda account: account.account_type == 'asset_receivable').ids)
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
            bank_statement.l10n_mx_edi_payment_document_ids.action_force_payment_cfdi()

        action_download = bank_statement.l10n_mx_edi_payment_document_ids[0].action_download_file()
        self.authenticate(self.env.user.login, self.env.user.login)
        res = self.url_open(action_download['url'])

        self.assertEqual(res.status_code, 200)
