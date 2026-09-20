from dateutil.relativedelta import relativedelta

from odoo.tests import freeze_time, tagged
from odoo.addons.l10n_co_dian import xml_utils

from .common import TestCoDianCommon


@freeze_time('2024-01-30')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCommercialEvents(TestCoDianCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # send invoice to our own company so we don't have to switch companies when sending events
        cls.yesterday = cls.frozen_today - relativedelta(days=1)
        cls.invoice = cls._create_move(
            partner_id=cls.company_data['company'].partner_id.id,
            freeze_date=cls.yesterday,
        )

        cls.bill_pending_document_data = {
            'state': 'invoice_accepted',
            'commercial_state': 'pending',
        }

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _create_commercial_event_bill(self, invoice):
        return self._create_move(
            freeze_date=self.yesterday,
            partner_id=self.company_data['company'].partner_id.id,
            move_type='in_invoice',
            invoice_date=self.yesterday,
            journal_id=self.company_data['default_journal_purchase'].id,
            ref=invoice.name,
            l10n_co_edi_cufe_cude_ref=invoice.l10n_co_edi_cufe_cude_ref,
        )

    def _get_status_event(self, invoice, response_file):
        with self._mock_build_and_send_request(response_file=response_file):
            invoice.l10n_co_dian_action_update_event_status()

    # -------------------------------------------------------------------------
    # TESTS
    # -------------------------------------------------------------------------

    def test_accept_by_customer(self):
        self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_warnings.xml')
        self.assertTrue(self.invoice.l10n_co_dian_attachment_id)
        self.assertTrue(self.invoice.l10n_co_edi_cufe_cude_ref)
        self.assertEqual(len(self.invoice.l10n_co_dian_document_ids), 1)
        invoice_document_pending_values = {
            'state': 'invoice_accepted',
            'commercial_state': 'pending',
        }
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids.sorted(), [invoice_document_pending_values])

        bill = self._create_commercial_event_bill(self.invoice)
        with self._mock_build_and_send_request('CommercialEvent.xml'):
            bill.l10n_co_dian_send_event_update_status_received()
        bill_identifier = bill.l10n_co_edi_cufe_cude_ref
        self.assertTrue(bill_identifier)
        self.assertEqual(len(bill.l10n_co_dian_document_ids), 2)
        self.assertTrue(bill.l10n_co_dian_document_ids[0].identifier)
        bill_document_received_values = {
            'state': 'invoice_accepted',
            'commercial_state': 'received',
        }
        self.assertRecordValues(bill.l10n_co_dian_document_ids.sorted(), [bill_document_received_values, self.bill_pending_document_data])

        # The document contains a history of the events, so will be different after each state change. It will be sent
        # by email to the vendor when the commercial state is updated, check if it is correct.
        validation_document = bill.l10n_co_dian_attachment_id
        xml = xml_utils._unzip(validation_document.raw)
        self._assert_document_dian(xml, 'l10n_co_dian/tests/attachments/commercial_event_attached_document.xml')

        with self._mock_build_and_send_request('CommercialEvent.xml'):
            bill.l10n_co_dian_send_event_update_status_goods_received()
        self.assertRecordValues(bill, [{'l10n_co_edi_cufe_cude_ref': bill_identifier}])
        self.assertEqual(len(bill.l10n_co_dian_document_ids), 3)
        bill_document_goods_received_values = {
            'state': 'invoice_accepted',
            'commercial_state': 'goods_received',
        }
        self.assertRecordValues(bill.l10n_co_dian_document_ids.sorted(), [
            bill_document_goods_received_values,
            bill_document_received_values,
            self.bill_pending_document_data,
        ])

        with self._mock_build_and_send_request('CommercialEvent.xml'):
            bill.l10n_co_dian_send_event_update_status_accepted()
        self.assertRecordValues(bill, [{'l10n_co_edi_cufe_cude_ref': bill_identifier}])
        self.assertEqual(len(bill.l10n_co_dian_document_ids), 4)
        bill_document_accepted_values = {
            'state': 'invoice_accepted',
            'commercial_state': 'accepted',
        }
        self.assertRecordValues(bill.l10n_co_dian_document_ids.sorted(), [
            bill_document_accepted_values,
            bill_document_goods_received_values,
            bill_document_received_values,
            self.bill_pending_document_data,
        ])

    def test_get_status_event(self):
        self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_warnings.xml')
        self.assertTrue(self.invoice.l10n_co_dian_attachment_id)
        self.assertEqual(len(self.invoice.l10n_co_dian_document_ids), 1)
        invoice_document_pending_values = {
            'state': 'invoice_accepted',
            'commercial_state': 'pending',
        }
        self.assertRecordValues(self.invoice.l10n_co_dian_document_ids.sorted(), [invoice_document_pending_values])
        self.assertTrue(self.invoice.l10n_co_dian_document_ids.identifier)
        self.assertRecordValues(self.invoice, [{
            'l10n_co_edi_cufe_cude_ref': self.invoice.l10n_co_dian_document_ids.identifier,
        }])

        bill = self._create_commercial_event_bill(self.invoice)

        # GetStatusEvent while no events have been sent yet
        self._get_status_event(self.invoice, 'GetStatusEvent_no_events.xml')
        self.assertEqual(len(self.invoice.l10n_co_dian_document_ids), 2)
        invoice_rejected_document_values = {
            'state': 'invoice_rejected',
            'commercial_state': False,
        }
        documents = self.invoice.l10n_co_dian_document_ids.sorted()
        self.assertRecordValues(self.invoice, [{
            'l10n_co_edi_cufe_cude_ref': documents[-1].identifier,
        }])
        self.assertRecordValues(documents, [
            invoice_rejected_document_values,
            invoice_document_pending_values,
        ])
        self.assertRecordValues(documents[0], [{
            'message': "<p>EL CUFE o Factura consultada no tiene a la fecha eventos asociados.</p>",
        }])

        # GetStatusEvent after event has been sent
        with self._mock_build_and_send_request('CommercialEvent.xml'):
            bill.l10n_co_dian_send_event_update_status_received()
        self.assertEqual(len(bill.l10n_co_dian_document_ids), 2)
        bill_document_received_values = {
            'state': 'invoice_accepted',
            'commercial_state': 'received',
        }
        self.assertRecordValues(bill.l10n_co_dian_document_ids.sorted(), [bill_document_received_values, self.bill_pending_document_data])

        self._get_status_event(self.invoice, 'GetStatusEvent_received.xml')
        documents = self.invoice.l10n_co_dian_document_ids.sorted()
        self.assertEqual(len(documents), 2)
        invoice_document_received_values = {
            'state': 'invoice_accepted',
            'commercial_state': 'received',
        }
        self.assertRecordValues(documents, [
            invoice_document_received_values,
            invoice_document_pending_values,
        ])
        self.assertRecordValues(self.invoice, [{
            'l10n_co_edi_cufe_cude_ref': documents[-1].identifier,
        }])

        # GetStatusEvent after a second event
        with self._mock_build_and_send_request('CommercialEvent.xml'):
            bill.l10n_co_dian_send_event_update_status_goods_received()
        self.assertEqual(len(bill.l10n_co_dian_document_ids), 3)
        bill_document_goods_received_values = {
            'state': 'invoice_accepted',
            'commercial_state': 'goods_received',
        }
        self.assertRecordValues(bill.l10n_co_dian_document_ids.sorted(), [
            bill_document_goods_received_values,
            bill_document_received_values,
            self.bill_pending_document_data,
        ])

        self._get_status_event(self.invoice, 'GetStatusEvent_goods_received.xml')
        documents = self.invoice.l10n_co_dian_document_ids.sorted()
        self.assertEqual(len(documents), 3)
        invoice_document_goods_received_values = {
            'state': 'invoice_accepted',
            'commercial_state': 'goods_received',
        }
        self.assertRecordValues(documents, [
            invoice_document_goods_received_values,
            invoice_document_received_values,
            invoice_document_pending_values,
        ])
        self.assertRecordValues(self.invoice, [{
            'l10n_co_edi_cufe_cude_ref': documents[-1].identifier,
        }])
