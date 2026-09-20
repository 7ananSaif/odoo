import base64

from odoo.addons.account_edi.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_pe_edi.tests.common import TestPeEdiCommon
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.point_of_sale.tests.test_generic_localization import TestGenericLocalization
from odoo.tests import tagged
from odoo import Command, fields
from unittest.mock import patch
from lxml import etree
from lxml import objectify


def mocked_l10n_pe_edi_post_invoice_sign_web_service(edi_format, invoice, edi_filename, edi_str):
    # sign the EDI
    edi_tree = objectify.fromstring(edi_str)
    signed_edi = edi_format._l10n_pe_sign(invoice.company_id.sudo().l10n_pe_edi_certificate_id, edi_tree)
    edi_str = etree.tostring(signed_edi, xml_declaration=True, encoding='ISO-8859-1')
    zip_edi_str = edi_format._l10n_pe_edi_zip_edi_document([('%s.xml' % edi_filename, edi_str)])
    return {
        'attachment': edi_format.env['ir.attachment'].create({
            'res_model': invoice._name,
            'res_id': invoice.id,
            'type': 'binary',
            'name': '%s.zip' % edi_filename,
            'datas': base64.encodebytes(zip_edi_str),
            'mimetype': 'application/zip',
        })
    }


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPeEdiPoS(TestPeEdiCommon, TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].l10n_pe_edi_provider = 'digiflow'
        edi_format = cls.env['account.edi.format'].search([("code", "=", "pe_ubl_2_1")])
        cls.main_pos_config.invoice_journal_id.write({
            "edi_format_ids": [Command.link(edi_format.id)]
        })

    def test_invoice_signed_qr_code(self):
        with patch(
            "odoo.addons.l10n_pe_edi.models.account_edi_format.AccountEdiFormat._l10n_pe_edi_post_invoice_web_service",
            new=mocked_l10n_pe_edi_post_invoice_sign_web_service,
        ):
            self.main_pos_config.open_ui()
            self.main_pos_config.invoice_journal_id.l10n_latam_use_documents = True

            # We need to assign a new journal to the PoS that do not use l10n_latam_use_documents
            self.main_pos_config.journal_id = self.env["account.journal"].create(
                {
                    "type": "general",
                    "name": "Point of Sale - Test",
                    "code": "POSS - Test",
                    "company_id": self.env.company.id,
                    "sequence": 20,
                }
            )
            order_data = {
                "amount_paid": 1180,
                "amount_tax": 180,
                "amount_return": 0,
                "amount_total": 1180,
                "date_order": fields.Datetime.to_string(fields.Datetime.now()),
                "fiscal_position_id": False,
                "lines": [
                    Command.create({
                        "discount": 0,
                        "pack_lot_ids": [],
                        "price_unit": 1000.0,
                        "product_id": self.product_a.id,
                        "price_subtotal": 1000.0,
                        "price_subtotal_incl": 1180.0,
                        "tax_ids": [[6, False, [self.product_a.taxes_id[0].id]]],
                        "qty": 1,
                    }),
                ],
                "name": "Order 12345-123-1234",
                "partner_id": self.partner_a.id,
                "session_id": self.main_pos_config.current_session_id.id,
                "sequence_number": 2,
                "payment_ids": [
                        Command.create({
                            "amount": 1180,
                            "name": fields.Datetime.now(),
                            "payment_method_id": self.bank_payment_method.id,
                        }),
                ],
                "uuid": "12345-123-1234",
                "last_order_preparation_change": "{}",
                "user_id": self.env.uid,
                "to_invoice": True,
            }

            order = self.env["pos.order"].sync_from_ui([order_data])["pos.order"][0]
            invoice_str = str(self.env["pos.order"].browse(order["id"]).account_move._get_invoice_legal_documents('pdf', allow_fallback=True).get('content'))
            self.assertTrue("barcode_type=QR" in invoice_str)

    def test_refund_reason_not_set(self):
        """
        Test that a refund in Peruvian PoS does not crash and sets the refund reason.
        """
        self.main_pos_config.open_ui()
        session = self.main_pos_config.current_session_id
        order_result = self.env["pos.order"].sync_from_ui([{
            "amount_paid": 1180,
            "amount_tax": 180,
            "amount_return": 0,
            "amount_total": 1180,
            "lines": [
                Command.create({
                    "price_unit": 1000.0,
                    "product_id": self.product_a.id,
                    "price_subtotal": 1000.0,
                    "price_subtotal_incl": 1180.0,
                    "tax_ids": [Command.set([self.product_a.taxes_id[0].id])],
                    "qty": 1,
                }),
            ],
            "name": "Order 12345-123-1234",
            "partner_id": self.partner_a.id,
            "session_id": session.id,
            "payment_ids": [
                Command.create({
                    "amount": 1180,
                    "name": fields.Datetime.now(),
                    "payment_method_id": self.bank_payment_method.id,
                }),
            ],
            "uuid": "12345-123-1234",
            "to_invoice": True,
        }])
        original_order = self.env["pos.order"].browse(order_result["pos.order"][0]["id"])
        refund_order = self.env["pos.order"].create({
            "session_id": session.id,
            "partner_id": original_order.partner_id.id,
            "lines": [Command.create({
                "product_id": self.product_a.id,
                "qty": -1.0,
                "price_unit": 1000.0,
                "tax_ids": [Command.set([self.product_a.taxes_id[0].id])],
                "price_subtotal": -1000.0,
                "price_subtotal_incl": -1180.0,
            })],
            "refunded_order_id": original_order.id,
            "to_invoice": True,
            "amount_total": -1180.0,
            "amount_tax": -180.0,
            "amount_paid": -1180.0,
            "amount_return": 0.0,
            'is_refund': True,
        })
        refund_order.refunded_order_id = original_order
        try:
            refund_invoice = refund_order._generate_pos_order_invoice()
        except TypeError as e:
            self.fail(f'l10n_pe_edi_refund_reason should be able to not be set: {e}')
        # To make sure the l10n_pe_edi_refund_reason is still set as it should
        refund_order.write({"l10n_pe_edi_refund_reason": "01"})
        refund_invoice = refund_order._generate_pos_order_invoice()
        self.assertEqual(refund_invoice.l10n_pe_edi_refund_reason, "01")


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestGenericPE(TestGenericLocalization):
    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
