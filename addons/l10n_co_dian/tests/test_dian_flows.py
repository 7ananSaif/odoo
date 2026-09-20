from datetime import datetime
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import freeze_time, tagged

from .common import TestCoDianCommon


@freeze_time('2024-01-30')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDianFlows(TestCoDianCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invoice = cls._create_move()

    def _send_test_set_async(self):
        self.invoice.company_id.l10n_co_dian_test_environment = True
        self.invoice.company_id.l10n_co_dian_certification_process = True

        # Step 1: SendTestSetAsync
        self._mock_send_and_print(move=self.invoice, response_file='SendTestSetAsync.xml')

        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': '42424242',
            'state': 'invoice_pending',
            'message': "<p>Invoice is being processed by the DIAN.</p>",
        }])
        self.assertEqual(self.invoice.l10n_co_dian_state, 'invoice_pending')

    # ==== Get Status Zip ==== #

    def test_get_status_zip_warnings(self):
        """ SendTestSetAsync then GetStatusZip which returns warnings but the document is valid. """
        # Step 1: SendTestSetAsync
        self._send_test_set_async()
        # Step 2: GetStatusZip
        self._mock_get_status_zip(move=self.invoice, response_file='GetStatusZip_warnings.xml')

        # checks on the document
        self.assertEqual(len(self.invoice.l10n_co_dian_document_ids), 1)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': '42424242',
            'state': 'invoice_accepted',
            'message': (
                "<p>Procesado Correctamente.</p>"
                "<ul><li>Regla: FAJ44b, Notificación: Nit o Documento de Identificación BlaBlaBla.</li>"
                "<li>Regla: FAJ43b, Notificación: Nombre informado No corresponde al BlaBlaBla.</li></ul>"
            ),
        }])
        # checks on the invoice
        self.assertTrue(self.invoice.l10n_co_dian_attachment_id)
        self.assertEqual(self.invoice.l10n_co_dian_state, 'invoice_accepted')

    def test_get_status_zip_habilitation(self):
        """ SendTestSetAsync then GetStatusZip which inform that they passed the habitation process. """
        # Step 1: SendTestSetAsync
        self._send_test_set_async()
        # Step 2: GetStatusZip
        self._mock_get_status_zip(move=self.invoice, response_file='GetStatusZip_habilitation.xml')

        # checks on the document
        self.assertEqual(len(self.invoice.l10n_co_dian_document_ids), 1)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': '42424242',
            'state': 'invoice_rejected',
            'message': "<p>Set de prueba con identificador 123456 se encuentra Aceptado.</p>",
        }])
        # checks on the invoice
        self.assertFalse(self.invoice.l10n_co_dian_attachment_id)
        self.assertEqual(self.invoice.l10n_co_dian_state, 'invoice_rejected')

    def test_get_status_zip_pending(self):
        """ SendTestSetAsync then GetStatusZip which responds 'Batch is being processed' (need to check again later)"""
        # Step 1: SendTestSetAsync
        self._send_test_set_async()
        # Step 2: GetStatusZip
        self._mock_get_status_zip(move=self.invoice, response_file='GetStatusZip_pending.xml')

        # checks on the document
        self.assertEqual(len(self.invoice.l10n_co_dian_document_ids), 1)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': '42424242',
            'state': 'invoice_pending',
            'message': "<p>Batch en proceso de validación.</p>",
            'show_button_get_status': True,
        }])
        # checks on the invoice
        self.assertFalse(self.invoice.l10n_co_dian_attachment_id)
        self.assertEqual(self.invoice.l10n_co_dian_state, 'invoice_pending')

        # Step 3: GetStatusZip again (this time the document is processed)
        self._mock_get_status_zip(move=self.invoice, response_file='GetStatusZip_warnings.xml')

        # checks on the document
        self.assertEqual(len(self.invoice.l10n_co_dian_document_ids), 1)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': '42424242',
            'state': 'invoice_accepted',
            'message': (
                "<p>Procesado Correctamente.</p>"
                "<ul><li>Regla: FAJ44b, Notificación: Nit o Documento de Identificación BlaBlaBla.</li>"
                "<li>Regla: FAJ43b, Notificación: Nombre informado No corresponde al BlaBlaBla.</li></ul>"
            ),
        }])
        # checks on the invoice
        self.assertTrue(self.invoice.l10n_co_dian_attachment_id)
        self.assertEqual(self.invoice.l10n_co_dian_state, 'invoice_accepted')

    # ==== Send Bill Sync ==== #

    def test_send_bill_sync_warnings(self):
        """ SendBillSync returning warnings but the document is valid. """
        self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_warnings.xml')

        self.assertTrue(self.invoice.l10n_co_dian_attachment_id)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': False,
            'state': 'invoice_accepted',
            'message':  (
                "<p>Procesado Correctamente.</p>"
                "<ul><li>Regla: FAJ44b, Notificación: Nit o Documento de Identificación informado No BlaBlaBla.</li>"
                "<li>Regla: FAJ43b, Notificación: Nombre informado No corresponde al registrado en el BlaBlaBla.</li></ul>"
            ),
        }])

    def test_send_bill_sync_errors(self):
        """ SendBillSync returning errors blocking the Send & Print flow. """
        error_raised = False
        try:
            self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_errors.xml')
        except UserError as e:
            error_raised = True
            self.assertEqual(e.args[0], "Error(s) when sending the document to the DIAN:\n"
                                        "- Regla: ZB01, Rechazo: Fallo en el esquema XML del archivo")

        self.assertTrue(error_raised)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': False,
            'state': 'invoice_rejected',
            'message': "<p>Documento con errores en campos mandatorios.</p>"
                       "<ul><li>Regla: ZB01, Rechazo: Fallo en el esquema XML del archivo</li></ul>",
        }])

    def test_send_bill_sync_errors_nsmap(self):
        """ SendBillSync returning errors due to a missing namespace, blocking the Send & Print flow. """
        error_raised = False
        try:
            self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_errors_nsmap.xml')
        except UserError as e:
            error_raised = True
            self.assertEqual(e.args[0], "Error(s) when sending the document to the DIAN:\n- Error al parsear xml. Namespace prefix 'sts' is not defined.")

        self.assertTrue(error_raised)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': False,
            'state': 'invoice_rejected',
            'message': "<p>Error al parsear xml. Namespace prefix 'sts' is not defined.</p>",
        }])

    def test_send_bill_sync_duplicated(self):
        """ SendBillSync returning 'Regla: 90, Rechazo: Documento procesado anteriormente.'
        This means an invoice with the same CUFE has already been accepted by the DIAN.
        """
        error_raised = False
        try:
            self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_duplicated.xml')
        except UserError as e:
            error_raised = True

        self.assertFalse(error_raised)
        self.assertTrue(self.invoice.l10n_co_dian_attachment_id)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': False,
            'state': 'invoice_accepted',
            'message': ("<p>Validación contiene errores en campos mandatorios.</p>"
                        "<ul><li>Regla: 90, Rechazo: Documento procesado anteriormente.</li></ul>"),
        }])

    def test_send_bill_sync_second_attempt(self):
        """ First attempt SendBillSync returns errors, second attempt is successful. """
        # 1st attempt (fail)
        self.test_send_bill_sync_errors()

        self.assertFalse(self.invoice.l10n_co_dian_attachment_id)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': False,
            'state': 'invoice_rejected',
            'message': "<p>Documento con errores en campos mandatorios.</p>"
                       "<ul><li>Regla: ZB01, Rechazo: Fallo en el esquema XML del archivo</li></ul>",
        }])

        # 2nd attempt (success without errors or warnings)
        with patch(f'{self.document_path}._parse_errors', return_value=[]):
            self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_warnings.xml')

        self.assertEqual(len(self.invoice.l10n_co_dian_document_ids), 1)  # no need to keep the rejected documents
        self.assertTrue(self.invoice.l10n_co_dian_attachment_id)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': False,
            'state': 'invoice_accepted',
            'message': "<p>Procesado Correctamente.</p>",
        }])

    def test_send_bill_sync_unknown_error(self):
        """ Handle the generic error returned when using wrong certificates (e.g. the demo certificate). """
        error_raised = False
        try:
            self._mock_send_and_print(move=self.invoice, response_file='unknown_error.xml', response_code=500)
        except UserError as e:
            error_raised = True
            self.assertEqual(e.args[0], "Error(s) when sending the document to the DIAN:\n"
                                        "- The creator of this fault did not specify a Reason. "
                                        "(This might be caused by using incorrect certificates)")
        self.assertTrue(error_raised)
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids, [{
            'zip_key': False,
            'state': 'invoice_sending_failed',
            'message': "<p>The creator of this fault did not specify a Reason. "
                       "(This might be caused by using incorrect certificates)</p>",
        }])

    def test_send_bill_sync_support_document(self):
        """ Send Support Document. """
        bill = self._create_move(
            move_type='in_invoice',
            invoice_date=datetime.today(),
            journal_id=self.support_document_journal.id,
        )
        with (
            patch(f'{self.utils_path}._build_and_send_request', return_value=self._mocked_response('SendBillSync_warnings.xml', 200)),
            self._disable_get_acquirer_call(),
        ):
            bill.l10n_co_dian_action_send_bill_support_document()

        self.assertTrue(bill.l10n_co_dian_attachment_id)
        self.assertRecordValues(bill.l10n_co_dian_document_ids, [{
            'zip_key': False,
            'state': 'invoice_accepted',
            'message': "<p>Procesado Correctamente.</p>"
                       "<ul><li>Regla: FAJ44b, Notificación: Nit o Documento de Identificación informado No BlaBlaBla.</li>"
                       "<li>Regla: FAJ43b, Notificación: Nombre informado No corresponde al registrado en el BlaBlaBla.</li></ul>",
        }])

    def test_get_acquirer(self):
        """ Get Partner Data """
        partner = self._create_partner(
            country_id=self.env.ref('base.co').id,
            vat='213123432-1',
            email='test@mail.com',
        )

        with patch(f'{self.utils_path}._build_and_send_request', return_value=self._mocked_response('GetAcquirer_partner.xml', 200)):
            partner.button_l10n_co_dian_refresh_data()

        self.assertRecordValues(partner, [{
            'name': 'Real Company Name',
            'email': 'company@mail.com',
        }])


@freeze_time('2024-01-30')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDianFlowsSettings(TestCoDianCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['res.config.settings'].create({})
        cls.settings.l10n_co_dian_test_environment = True
        cls.settings.l10n_co_dian_certification_process = True
        cls.settings.l10n_co_dian_cert_invoice_count = 2
        cls.settings.l10n_co_dian_cert_credit_count = 2
        cls.settings.l10n_co_dian_cert_debit_count = 2

    def _mocked_build_and_send_request(self, record, payload, service, company):
        """Build_and_send_request is a module level function in xml_util that contains a parameter
        self. To be able to mock it from within the test class we need an additional parameter to
        make sure it can be called."""
        if service == 'SendTestSetAsync':
            return self._mocked_response('SendTestSetAsync.xml', 200)
        if service == 'GetStatusZip':
            return self._mocked_response('GetStatusZip_habilitation.xml', 200)
        return self._mocked_response('', 200)

    def test_certification_process(self):
        """ Test the certification process with the DIAN. """
        with (
            patch(f'{self.utils_path}._build_and_send_request', autospec=True, side_effect=self._mocked_build_and_send_request),
            self._disable_get_acquirer_call(),
        ):
            self.settings.action_l10n_co_certify_with_dian()
        # Check that the journals were created or updated.
        journals = self.env['account.journal'].search([('code', 'in', ['SETP', 'NC', 'ND'])])
        self.assertEqual(len(journals), 3)

        # Unique journal values
        self.assertRecordValues(journals, [
            {'code': 'SETP', 'l10n_co_edi_min_range_number': 990000000, 'l10n_co_edi_max_range_number': 995000000, 'l10n_co_edi_debit_note': False},
            {'code': 'NC', 'l10n_co_edi_min_range_number': 1, 'l10n_co_edi_max_range_number': 1000, 'l10n_co_edi_debit_note': False},
            {'code': 'ND', 'l10n_co_edi_min_range_number': 1, 'l10n_co_edi_max_range_number': 1000, 'l10n_co_edi_debit_note': True},
        ])

        # Shared journal values
        self.assertRecordValues(journals, [{
            'l10n_co_dian_technical_key': 'fc8eac422eba16e22ffd8c6f94b3f40a6e38162c',
            'l10n_co_edi_dian_authorization_date': fields.Date.from_string('2019-01-19'),
            'l10n_co_edi_dian_authorization_end_date': fields.Date.from_string('2030-01-19'),
            'l10n_co_edi_dian_authorization_number': '18760000001',
        }] * 3)

        # Check that the moves were created
        moves = self.env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('journal_id', 'in', journals.ids),
        ])
        self.assertEqual(len(moves), 6)

        # The test file we use is one already accepted so it should all be marked as already accepted.
        for move in moves:
            self.assertRecordValues(move.l10n_co_dian_document_ids, [{
                'zip_key': '42424242',
                'state': 'invoice_rejected',
                'message': "<p>Set de prueba con identificador 123456 se encuentra Aceptado.</p>",
            }])
