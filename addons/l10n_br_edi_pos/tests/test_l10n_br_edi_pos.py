# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re
from unittest.mock import patch

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.l10n_br_avatax.tests.test_br_avatax import TestBRMockedRequests
from odoo.addons.l10n_br_edi.tests.test_l10n_br_edi import TestL10nBREDICommon
from odoo.addons.l10n_br_edi_pos.tests.common import CommonPosBrEdiTest
from odoo.addons.l10n_br_edi_pos.models.pos_order import PosOrder
from odoo.exceptions import UserError
from odoo.tests import tagged, freeze_time
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.test_generic_localization import TestGenericLocalization

# All tested POS orders are mocked to use this ID when calculating the access key
TEST_POS_ORDER_ID = 548
TEST_DATETIME = "2025-02-05T22:55:17+00:00"


class TestL10nBREDIPOSCommon(TestL10nBREDICommon, TestBRMockedRequests):
    @classmethod
    def setUpClass(self):
        super().setUpClass()
        # Avoid taxes access error
        self.product_screens.taxes_id = [(5, 0)]
        self.product_cabinet.taxes_id = [(5, 0)]
        self.product_screens.available_in_pos = True
        self.company.write(
            {
                "l10n_br_edi_csc_number": "00001",
                "l10n_br_edi_csc_identifier": "000000000000000000000000000000000000",
                "l10n_br_avatax_api_identifier": "TEST",
                "l10n_br_avatax_api_key": "TEST",
                "vat": "49233848000150",
            }
        )

        # Information needed for BR Mock.
        self.mocked_l10n_br_iap_patches.append(patch(
            f"{PosOrder.__module__}.PosOrder._l10n_br_get_id_for_cnf", autospec=True, side_effect=lambda *args: TEST_POS_ORDER_ID
        ))


@tagged("post_install_l10n", "post_install", "-at_install")
class TestL10nBREDIPOS(TestL10nBREDIPOSCommon, CommonPosBrEdiTest):

    def setUp(self):
        super().setUp()
        self.pos_config_usd.order_seq_id.write({'number_next_actual': 1})

    def test_01_access_key_check_digit(self):
        self.assertEqual(
            self.env["pos.order"]._l10n_br_calculate_access_key_check_digit("4323070738511100010255503000765973124086659"),
            3,
        )

    @freeze_time(TEST_DATETIME)
    def test_02_session_closing(self):
        order, _ = self.create_backend_pos_order({
            'order_data': {
                'name': 'Order/0001',
            },
            'line_data': [{
                'qty': 3,
                'price_unit': 1.0,
                'product_id': self.product_screens.product_variant_id.id,
            }],
        })

        with self._with_mocked_l10n_br_iap_request([
            ("calculate_tax", "anonymous_tax_request", "anonymous_tax_response"),
            ("submit_invoice_goods", "anonymous_edi_request", "anonymous_edi_response"),
        ]):
            payment_context = {"active_ids": order.ids, "active_id": order.id}
            order_payment = self.env['pos.make.payment'].with_context(**payment_context).create({})
            order_payment.with_context(**payment_context).check()

        current_session = self.pos_config_usd.current_session_id
        current_session.action_pos_session_close()
        self.assertEqual(current_session.state, "closed")

    def _test_adjustment_entry(self, order, expected_communications, expected_adjustment_line_vals):
        order.l10n_br_last_avatax_status = "error"
        current_session = self.pos_config_usd.current_session_id
        self.env["pos.make.payment"].with_context(active_id=order.id).create({"amount": order.amount_total}).check()
        current_session.action_pos_session_close()
        self.assertEqual(current_session.state, "closed", "Session should be closed without differences.")

        with self._with_mocked_l10n_br_iap_request(expected_communications):
            order.button_l10n_br_edi()

        adjustment_entry = self.env["account.move"].search([("ref", "like", order.name)])
        self.assertEqual(len(adjustment_entry), 1, f"There should be one adjustment journal entry for {order.name}.")
        self.assertRecordValues(
            adjustment_entry.line_ids,
            expected_adjustment_line_vals,
        )

    @freeze_time(TEST_DATETIME)
    def test_03_edi_after_session_closed_simple(self):
        """Verify that a correcting journal entry is created if EDI is successfully retried after the session is closed."""
        order, _ = self.create_backend_pos_order({
            'line_data': [{
                'qty': 3,
                'product_id': self.product_screens.product_variant_id.id,
                "price_unit": 1.0,
            }],
        })
        expected_communications = [
            ("calculate_tax", "anonymous_tax_request", "anonymous_tax_response"),
            ("submit_invoice_goods", "anonymous_edi_request", "anonymous_edi_response"),
        ]
        expected_adjustment_line_vals = [
            {
                "account_id": order.lines.product_id._get_product_accounts()["income"].id,
                "amount_currency": 0.58,
            },
            {
                "account_id": self.env["account.account"].search([("code", "=", "2.01.01.09.03")]).id,  # icms
                "amount_currency": -0.58,
            },
        ]
        self._test_adjustment_entry(
            order,
            expected_communications,
            expected_adjustment_line_vals,
        )

    @freeze_time(TEST_DATETIME)
    def test_04_edi_after_session_closed_complex(self):
        """Verify the correcting journal entry posted after EDI is successfully retried in a closed session. Uses
        an order with multiple products that have different income accounts."""
        other_income_account = self.env["account.account"].search(
            [
                *self.env["account.account"]._check_company_domain(self.company),
                ("account_type", "=", "income"),
                ("id", "!=", self.company_data["default_account_revenue"].id),
            ],
            limit=1,
        )
        self.product_cabinet.property_account_income_id = other_income_account
        order, _ = self.create_backend_pos_order({
            'order_data': {
                "name": "Order/0002",
            },
            'line_data': [{
                'qty': 3,
                "price_unit": 1.0,
                'product_id': self.product_screens.product_variant_id.id,
            }, {
                'qty': 5,
                "price_unit": 3.0,
                'product_id': self.product_cabinet.product_variant_id.id,
            }],
        })
        expected_communications = [
            ("calculate_tax", "anonymous_tax_request_multiple_lines", "anonymous_tax_response_multiple_lines"),
            ("submit_invoice_goods", "anonymous_edi_request_multiple_lines", "anonymous_edi_response_multiple_lines"),
        ]
        expected_adjustment_line_vals = [
            {
                "account_id": self.product_screens._get_product_accounts()["income"].id,
                "amount_currency": 0.58,
            },
            {
                "account_id": other_income_account.id,
                "amount_currency": 2.93,
            },
            {
                "account_id": self.env["account.account"].search([("code", "=", "2.01.01.09.03")]).id,  # icms
                "amount_currency": -3.51,
            },
        ]
        self._test_adjustment_entry(
            order,
            expected_communications,
            expected_adjustment_line_vals,
        )

    @freeze_time(TEST_DATETIME)
    def test_05_edi_after_session_closed_different_product_same_account(self):
        """ Properly handle automatic adjustment entries that have multiple product lines with the same income account. """
        income_account = self.product_screens._get_product_accounts()["income"]
        self.assertEqual(income_account, self.product_cabinet._get_product_accounts()["income"])
        order, _ = self.create_backend_pos_order({
            'order_data': {
                "name": "Order/0002",
            },
            'line_data': [{
                'qty': 3,
                "price_unit": 1.0,
                'product_id': self.product_screens.product_variant_id.id,
            }, {
                'qty': 5,
                "price_unit": 3.0,
                'product_id': self.product_cabinet.product_variant_id.id,
            }],
        })
        expected_communications = [
            ("calculate_tax", "anonymous_tax_request_multiple_lines", "anonymous_tax_response_multiple_lines"),
            ("submit_invoice_goods", "anonymous_edi_request_multiple_lines", "anonymous_edi_response_multiple_lines"),
        ]
        expected_adjustment_line_vals = [
            {
                "account_id": income_account.id,
                "amount_currency": 0.58,
            },
            {
                "account_id": income_account.id,
                "amount_currency": 2.93,
            },
            {
                "account_id": self.env["account.account"].search([("code", "=", "2.01.01.09.03")]).id,  # icms
                "amount_currency": -3.51,
            },
        ]
        self._test_adjustment_entry(
            order,
            expected_communications,
            expected_adjustment_line_vals,
        )

    @freeze_time(TEST_DATETIME)
    def test_06_order_messages(self):
        order, _ = self.create_backend_pos_order({
            "order_data": {
                "name": "Order/0001",
            },
            "line_data": [{
                "qty": 3,
                "product_id": self.product_screens.product_variant_id.id,
                "price_unit": 1.0,
            }],
        })
        with self._with_mocked_l10n_br_iap_request(
            [
                ("calculate_tax", "anonymous_tax_request", "anonymous_tax_response"),
                ("submit_invoice_goods", "anonymous_edi_request", "anonymous_edi_response"),
            ]
        ):
            self.env["pos.make.payment"].with_context(active_id=order.id).create({"amount": order.amount_total}).check()

        self.assertRegex(order.message_ids[-2].body, ".*E-invoice submitted successfully.*")
        self.assertRegex(
            order.message_ids[-1].body,
            f".*{re.escape('<b>aa Regular Consumable Product</b><br>COFINS Incl. - R$&nbsp;0.00<br>ICMS Incl. - R$&nbsp;0.58<br>PIS Incl. - R$&nbsp;0.00')}.*"
        )

    @freeze_time(TEST_DATETIME)
    def test_07_failed_edi_ran_as_cron(self):
        """ Properly handle multiple orders being sent to the EDI in the background. This checks
        that only errored records can be sent to the EDI as well as mocking all network calls. """
        order_a, _ = self.create_backend_pos_order({
            'order_data': {
                'name': 'Order/0001',
            },
            'line_data': [{
                'qty': 3,
                'price_unit': 1.0,
                'product_id': self.product_screens.product_variant_id.id,
            }],
        })
        order_b, _ = self.create_backend_pos_order({
            'order_data': {
                "name": "Order/0002",
            },
            'line_data': [{
                'qty': 3,
                "price_unit": 1.0,
                'product_id': self.product_screens.product_variant_id.id,
            }, {
                'qty': 5,
                "price_unit": 3.0,
                'product_id': self.product_cabinet.product_variant_id.id,
            }],
        })

        orders = order_a + order_b
        for order in orders:
            order.l10n_br_last_avatax_status = "error"
            payment_context = {"active_ids": order.ids, "active_id": order.id}
            order_payment = self.env['pos.make.payment'].with_context(**payment_context).create({})
            order_payment.with_context(**payment_context).check()

        current_session = self.pos_config_usd.current_session_id
        current_session.action_pos_session_close()
        self.assertEqual(current_session.state, "closed", "Session should be closed without differences.")

        # Order B is accepted so it can't be sent.
        order_b.l10n_br_last_avatax_status = "accepted"
        with self.assertRaisesRegex(UserError, r".+Order/0002.+", msg="Action should have blocked the cron when a non-errored Order is selected"):
            orders.action_send_nfce_batch()

        order_b.l10n_br_last_avatax_status = "error"
        # Process
        results = orders.action_send_nfce_batch()
        self.assertEqual(results['type'], 'ir.actions.client')
        self.assertEqual(results['params']['next']['type'], 'ir.actions.act_window_close')

        # Await the CRON.
        self.assertEqual(order_a.l10n_br_edi_triggered_user_id, self.env.user, "Triggered User was not set to the right user")
        self.assertEqual(order_b.l10n_br_edi_triggered_user_id, self.env.user, "Triggered User was not set to the right user")

        expected_communications = [
            ("calculate_tax", "anonymous_tax_request", "anonymous_tax_response"),
            ("submit_invoice_goods", "anonymous_edi_request", "anonymous_edi_response"),
            ("calculate_tax", "anonymous_tax_request_multiple_lines", "anonymous_tax_response_multiple_lines"),
            ("submit_invoice_goods", "anonymous_edi_request_multiple_lines", "anonymous_edi_response_multiple_lines"),
        ]

        with self._with_mocked_l10n_br_iap_request(expected_communications), self.enter_registry_test_mode():
            self.env.ref('l10n_br_edi_pos.ir_cron_l10n_br_edi_pos_check_status').method_direct_trigger()

        self.assertEqual(order_a.l10n_br_edi_triggered_user_id.id, False, "Triggered User was not cleared")
        self.assertEqual(order_b.l10n_br_edi_triggered_user_id.id, False, "Triggered User was not cleared")

        self.assertEqual(order_a.l10n_br_last_avatax_status, "accepted", "Order was not properly processed")
        self.assertEqual(order_b.l10n_br_last_avatax_status, "accepted", "Order was not properly processed")

    @freeze_time(TEST_DATETIME)
    def test_08_order_no_payments(self):
        """ POS Orders with no payments due to 0 cost should always have paymentMode sent otherwise
            Avalara will error."""
        order, _ = self.create_backend_pos_order({
            'order_data': {
                'name': "Order/0001",
            },
            'line_data': [{
                'qty': 3,
                'price_unit': 0.0,
                'price_subtotal': 0.0,
                'price_subtotal_incl': 0.0,
                'product_id': self.product_screens.product_variant_id.id,
            }],
        })

        payload = order._prepare_l10n_br_avatax_document_service_call(order._get_l10n_br_avatax_service_params())
        expected_dict = {
            'paymentInfo': {
                'paymentMode': [
                    {
                        "mode": "99",
                        "value": 0.0,
                        "modeDescription": "Other",
                    },
                ],
            },
        }
        self.assertDictEqual(payload['header']['payment'], expected_dict, 'paymentMode should still be set for free orders!')

    def test_09_order_name(self):
        # Test that the order name uses the NFCE sequence number as expected
        self.pos_config_usd.order_seq_id.write({'number_next_actual': 5})

        self.pos_config_usd.open_ui()
        order = self.env['pos.order'].create({
            "name": "/",
            "pos_reference": "Order 12345-123-1234",
            'company_id': self.env.company.id,
            'session_id': self.pos_config_usd.current_session_id.id,
            'partner_id': self.partner_a.id,
            'access_token': '1234567890',
            'lines': [],
            'amount_tax': 0,
            'amount_total': 0,
            'amount_paid': 0,
            'amount_return': 0,
        })
        order.write({'state': 'paid'})
        self.assertEqual(order.name, 'PoS Config USD - 5')

        order_2 = self.env['pos.order'].create({
            "name": "/",
            "pos_reference": "Order 12345-123-1235",
            'company_id': self.env.company.id,
            'session_id': self.pos_config_usd.current_session_id.id,
            'partner_id': self.partner_a.id,
            'access_token': '1234567891',
            'lines': [],
            'amount_tax': 0,
            'amount_total': 0,
            'amount_paid': 0,
            'amount_return': 0,
        })
        order_2.write({'state': 'paid'})
        self.assertEqual(order_2.name, 'PoS Config USD - 6')


@freeze_time(TEST_DATETIME)
@tagged("post_install_l10n", "post_install", "-at_install")
class TestUi(TestL10nBREDIPOSCommon, TestPointOfSaleHttpCommon):
    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.main_pos_config.write(
            {
                "l10n_br_is_nfce": True,
                "l10n_br_invoice_serial": "1",
            }
        )
        self.main_pos_config.payment_method_ids.write({"l10n_br_payment_method": "01"})
        self.product_screens.write(
            {
                "list_price": 1.0,
                "taxes_id": False,
            }
        )
        self.product_cabinet.write(
            {
                "taxes_id": self.env["account.tax"].create(
                    {"name": "Excluded Tax", "amount": 10.0, "price_include_override": "tax_excluded"}
                ),
                "available_in_pos": True,
            }
        )

    def setUp(self):
        super().setUp()
        self.main_pos_config.order_seq_id.number_next_actual = 1  # the mocked requests expect orders to be the first

    def test_01_anonymous_order(self):
        with self._with_mocked_l10n_br_iap_request(
            [
                ("calculate_tax", "anonymous_tax_request", "anonymous_tax_response"),
                ("submit_invoice_goods", "anonymous_edi_request", "anonymous_edi_response"),
            ]
        ):
            self.start_tour(
                "/pos/ui/%d" % self.main_pos_config.id,
                "l10n_br_edi_pos.tour_anonymous_order",
                login=self.env.user.login,
            )

    def test_02_customer_order(self):
        with self._with_mocked_l10n_br_iap_request(
            [
                ("calculate_tax", "customer_tax_request", "customer_tax_response"),
                ("submit_invoice_goods", "customer_edi_request", "customer_edi_response"),
            ]
        ):
            self.start_tour(
                "/pos/ui/%d" % self.main_pos_config.id, "l10n_br_edi_pos.tour_customer_order", login=self.env.user.login
            )

            order = self.env['pos.order'].search([], limit=1, order='id desc')
            self.assertEqual(order.is_invoiced, False)

    def test_03_company_order(self):
        self.partner_customer.company_type = 'company'

        with self._with_mocked_l10n_br_iap_request(
            [
                ("calculate_tax", "company_tax_request", "company_tax_response"),
                ("submit_invoice_goods", "company_edi_request", "company_edi_response"),
            ]
        ):
            self.start_tour(
                "/pos/ui?config_id=%d" % self.main_pos_config.id, "l10n_br_edi_pos.tour_customer_order", login=self.env.user.login
            )

            order = self.env['pos.order'].search([], limit=1, order='id desc')
            self.assertEqual(order.is_invoiced, False)


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestGenericBR(TestGenericLocalization, TestL10nBREDIPOSCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country('br')
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.company_id.name = 'Company BR'
        cls.main_pos_config.write(
            {
                "l10n_br_is_nfce": True,
                "l10n_br_invoice_serial": "1",
            }
        )
        cls.main_pos_config.company_id.write({
            "name": "Company BR"
        })
        cls.wall_shelf.write({
            'taxes_id': False,
        })
        cls.whiteboard_pen.write({
            'taxes_id': False,
        })
