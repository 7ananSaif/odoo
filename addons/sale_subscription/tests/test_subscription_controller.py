# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
import json
from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import Command, http
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger
from odoo.tools.misc import get_lang

from odoo.addons.http_routing.tests.common import MockRequest
from odoo.addons.payment.tests.common import PaymentCommon
from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged("post_install", "-at_install", "subscription_controller")
class TestSubscriptionController(PaymentHttpCommon, PaymentCommon, TestSubscriptionCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.pricing_month = cls.sub_product_tmpl.subscription_rule_ids.filtered(
            lambda rule: rule.plan_id == cls.plan_month
        )
        cls.pricing_year = cls.sub_product_tmpl.subscription_rule_ids.filtered(
            lambda rule: rule.plan_id == cls.plan_year
        )

        # FIXME dunno why we need to recreate the test product here when it's 'nearly' identical to
        # the one in the TestSubscriptionCommon, but some tests fail without it, so keeping it for
        # now.
        cls.sub_product_tmpl = cls.ProductTmpl.sudo().create({
            'name': 'TestProduct',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': cls.uom_unit.id,
        })
        cls.pricing_month = cls.pricing_month.copy({'product_tmpl_id': cls.sub_product_tmpl.id})
        cls.pricing_year = cls.pricing_year.copy({'product_tmpl_id': cls.sub_product_tmpl.id})
        cls.subscription_tmpl = cls.env['sale.order.template'].create({
            'name': 'Subscription template without discount',
            'duration_unit': 'year',
            'is_unlimited': False,
            'duration_value': 2,
            'note': "This is the template description",
            'plan_id': cls.plan_month.id,
            'sale_order_template_line_ids': [
                Command.create({
                    'name': "monthly",
                    'product_id': cls.sub_product_tmpl.product_variant_ids.id,
                    'product_uom_qty': 1,
                    'product_uom_id': cls.sub_product_tmpl.uom_id.id
                }),
                Command.create({
                    'name': "yearly",
                    'product_id': cls.sub_product_tmpl.product_variant_ids.id,
                    'product_uom_qty': 1,
                    'product_uom_id': cls.sub_product_tmpl.uom_id.id,
                }),
            ]
        })

    def setUp(self):
        super().setUp()

        self.user = new_test_user(self.env, "test_user_1", email="test_user_1@nowhere.com", tz="UTC")
        self.other_user = new_test_user(self.env, "test_user_2", email="test_user_2@nowhere.com", password="P@ssw0rd!", tz="UTC")

        self.partner = self.user.partner_id
        # Test Subscription
        self.subscription = self.SaleOrder.create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'note': "original subscription description",
            'partner_id': self.other_user.partner_id.id,
            'pricelist_id':  self.other_user.property_product_pricelist.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        self.subscription._onchange_sale_order_template_id()
        self.subscription.end_date = False  # reset the end_date
        self.subscription_tmpl.flush_recordset()
        self.subscription.flush_recordset()

    def _pause_subscription(self, until_date):
        """ method to pause a subscription from protal."""
        data = {
            "access_token": self.subscription.access_token,
            "csrf_token": http.Request.csrf_token(self),
            "until": until_date,
        }
        return self.url_open(f"/my/subscriptions/{self.subscription.id}/pause", allow_redirects=False, data=data)

    def _resume_subscription(self):
        """ method to resume a subscription from protal."""
        data = {
            "access_token": self.subscription.access_token,
            "csrf_token": http.Request.csrf_token(self),
        }
        return self.url_open(f"/my/subscriptions/{self.subscription.id}/resume", allow_redirects=False, data=data)

    def test_close_contract(self):
        """ Test subscription close """
        with freeze_time("2021-11-18"):
            self.authenticate(None, None)
            self.subscription.plan_id.user_closable = True
            self.subscription.action_confirm()
            close_reason_id = self.env.ref('sale_subscription.close_reason_1')
            data = {'access_token': self.subscription.access_token, 'csrf_token': http.Request.csrf_token(self),
                    'close_reason_id': close_reason_id.id, 'closing_text': "I am broke"}
            url = "/my/subscriptions/%s/close" % self.subscription.id
            res = self.url_open(url, allow_redirects=False, data=data)
            self.assertEqual(res.status_code, 303)
            self.env.invalidate_all()
            self.assertEqual(self.subscription.subscription_state, '6_churn', 'The subscription should be closed.')
            self.assertEqual(self.subscription.end_date, date(2021, 11, 18), 'The end date of the subscription should be updated.')

    def test_prevents_assigning_not_owned_payment_tokens_to_subscriptions(self):
        malicious_user_subscription = self.env['sale.order'].create({
            'name': 'Free Subscription',
            'partner_id': self.malicious_user.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        malicious_user_subscription._onchange_sale_order_template_id()

        legit_user_subscription = self.env['sale.order'].create({
            'name': 'Free Subscription',
            'partner_id': self.legit_user.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        stolen_payment_method = self.env['payment.token'].create(
            {'payment_details': 'Jimmy McNulty',
             'partner_id': self.malicious_user.partner_id.id,
             'provider_id': self.dummy_provider.id,
             'payment_method_id': self.payment_method_id,
             'provider_ref': 'Omar Little'})
        legit_payment_method = self.env['payment.token'].create(
            {'payment_details': 'Jimmy McNulty',
             'partner_id': self.legit_user.partner_id.id,
             'provider_id': self.dummy_provider.id,
             'payment_method_id': self.payment_method_id,
             'provider_ref': 'Legit ref'})
        legit_user_subscription._portal_ensure_token()
        malicious_user_subscription._portal_ensure_token()
        # Payment Token exists/does not exists
        # Payment Token is accessible to user/not accessible
        # SO accessible to User/Accessible thanks to the token/Not Accessible (wrong token, no token)
        # First we check a legit token assignation for a legit subscription.
        self.authenticate('ness', 'nessnessness')
        data = {'token_id': legit_payment_method.id,
                'order_id': legit_user_subscription.id,
                'access_token': legit_user_subscription.access_token
                }
        url = self._build_url("/my/subscriptions/assign_token/%s" % legit_user_subscription.id)
        self.make_jsonrpc_request(url, data)
        legit_user_subscription.invalidate_recordset()
        self.assertEqual(legit_user_subscription.payment_token_id, legit_payment_method)
        data = {'token_id': 9999999999999999, 'order_id': legit_user_subscription.id}
        with self._assertNotFound():
            self.make_jsonrpc_request(url, data)
        legit_user_subscription.invalidate_recordset()
        self.assertEqual(legit_user_subscription.payment_token_id, legit_payment_method, "The new token should be saved on the order.")

        # Payment token is inacessible to user but the SO is OK
        self.authenticate('al', 'alalalal')
        data = {'token_id': legit_payment_method.id, 'order_id': malicious_user_subscription.id}
        url = self._build_url("/my/subscriptions/assign_token/%s" % malicious_user_subscription.id)
        with self._assertNotFound():
            self.make_jsonrpc_request(url, data)
        malicious_user_subscription.invalidate_recordset()
        self.assertFalse(malicious_user_subscription.payment_token_id, "No token should be saved on the order.")

        # The SO is not accessible but the token is mine
        data = {'token_id': stolen_payment_method.id, 'order_id': legit_user_subscription.id}
        url = self._build_url("/my/subscriptions/assign_token/%s" % legit_user_subscription.id)
        with self._assertNotFound():
            self.make_jsonrpc_request(url, data)
        legit_user_subscription.invalidate_recordset()
        self.assertEqual(legit_user_subscription.payment_token_id, legit_payment_method, "The token should not be updated")

    def test_automatic_invoice_token(self):
        self.original_prepare_invoice = self.subscription._prepare_invoice
        with patch('odoo.addons.sale_subscription.models.sale_order.SaleOrder._do_payment', wraps=self._mock_subscription_do_payment):
            self.env['ir.config_parameter'].sudo().set_param('sale.automatic_invoice', 'False')
            subscription = self._portal_payment_controller_flow()
            subscription.transaction_ids.unlink()
            # set automatic invoice and restart
            self.env['ir.config_parameter'].sudo().set_param('sale.automatic_invoice', 'True')
            self._portal_payment_controller_flow()

    def _portal_payment_controller_flow(self):
        subscription = self.subscription.create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'payment_token_id': self.payment_token.id,
            'sale_order_template_id': self.subscription_tmpl.id,

        })
        subscription._onchange_sale_order_template_id()
        subscription.state = 'sent'
        subscription._portal_ensure_token()
        signature = "R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs="  # BASE64 of a simple image
        data = {'order_id': subscription.id, 'access_token': subscription.access_token, 'signature': signature}

        url = self._build_url("/my/orders/%s/accept" % subscription.id)
        self.make_jsonrpc_request(url, data)
        data = {
            'provider_id': self.dummy_provider.id,
            'payment_method_id': self.payment_method_id,
            'token_id': None,
            'order_id': subscription.id,
            'access_token': subscription.access_token,
            'amount': subscription.amount_total,
            'flow': 'direct',
            'tokenization_requested': True,
            'landing_route': subscription.get_portal_url(),
        }
        url = self._build_url("/my/orders/%s/transaction" % subscription.id)
        self.make_jsonrpc_request(url, data)
        subscription.transaction_ids.provider_id.support_manual_capture = 'full_only'
        subscription.transaction_ids._set_authorized()
        subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
        subscription.transaction_ids.token_id = self.payment_token.id
        self.assertEqual(subscription.next_invoice_date, datetime.date.today())
        self.assertEqual(subscription.state, 'sale')
        subscription.transaction_ids._create_or_link_to_invoice()
        subscription.transaction_ids._post_process()  # Create the payment
        self.assertEqual(subscription.invoice_count, 1, "One invoice should be created")
        # subscription has a payment_token_id, the invoice is created by the flow.
        subscription.invoice_ids.invoice_line_ids.account_id.account_type = 'income'
        subscription.invoice_ids.auto_post = 'at_date'
        self.env.ref('account.ir_cron_auto_post_draft_entry').method_direct_trigger()
        self.assertTrue(subscription.next_invoice_date > datetime.date.today(), "the next invoice date should be updated")
        self.env['account.payment.register'] \
            .with_context(active_model='account.move', active_ids=subscription.invoice_ids.ids) \
            .create({
            'currency_id': subscription.currency_id.id,
            'amount': subscription.amount_total,
        })._create_payments()
        self.assertEqual(subscription.invoice_ids.mapped('state'), ['posted'])
        self.assertTrue(subscription.invoice_ids.payment_state in ['paid', 'in_payment'])
        subscription._cron_recurring_create_invoice()
        invoices = subscription.invoice_ids.filtered(lambda am: am.state in ['draft', 'posted']) # avoid counting canceled invoices
        self.assertEqual(len(invoices), 1, "Only one invoice should be created")
        # test transaction flow when paying from the portal
        self.assertEqual(len(subscription.transaction_ids), 1, "Only one transaction should be created")
        first_transaction_id = subscription.transaction_ids
        url = self._build_url("/my/subscriptions/%s/transaction" % subscription.id)
        amount_to_invoice = subscription.amount_to_invoice  # force a non null amount 2.3
        data = {'access_token': subscription.access_token,
                'landing_route': subscription.get_portal_url(),
                'provider_id': self.dummy_provider.id,
                'payment_method_id': self.payment_method_id,
                'token_id': False,
                'flow': 'direct',
                'amount': amount_to_invoice,
                }
        self.make_jsonrpc_request(url, data)
        last_transaction_id = subscription.transaction_ids - first_transaction_id
        # the transaction is associated to the invoice in tx._post_process()
        last_transaction_id._set_done()
        last_transaction_id._post_process()
        self.assertEqual(len(subscription.transaction_ids), 2)
        self.assertEqual(last_transaction_id.sale_order_ids, subscription)
        subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
        # subscription has a payment_token_id, the invoice is created by the flow.
        subscription.invoice_ids.invoice_line_ids.account_id.account_type = 'asset_cash'
        subscription.invoice_ids.auto_post = 'at_date'
        subscription.transaction_ids._set_done()
        last_invoice_date = subscription.next_invoice_date - subscription.plan_id.billing_period
        if last_invoice_date != datetime.date.today():
            # sometimes, the computed last_invoice_date is different than the start_date at this step.
            # it happens for example on the 31th of march:
            # next_invoice_date = 30th of April - billing period = 30th of March
            # but 31th of March + billing period = 30th of April too.
            # As this test is only making sure that the invoice is paid, we make sure to register the payment when necessary
            # registering the payment every time could trigger
            # UserError: You can't register a payment because there is nothing left to pay on the selected journal items.
            self.env['account.payment.register'] \
                .with_context(active_model='account.move', active_ids=subscription.invoice_ids.ids) \
                .create({
                'currency_id': subscription.currency_id.id,
                'amount': subscription.amount_total,
            })._create_payments()
        res = set(subscription.invoice_ids.mapped('payment_state')) & {'not_paid', 'partial'}
        self.assertFalse(res,
                         "All invoices should be in paid or in_payment status")
        return subscription

    def test_controller_transaction_refund(self):
        self.original_prepare_invoice = self.subscription._prepare_invoice
        self.pricing_month.fixed_price = 10
        subscription = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'payment_token_id': self.payment_token.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        subscription._onchange_sale_order_template_id()
        subscription.order_line.product_uom_qty = 2
        self.assertEqual(subscription.order_line.pricelist_item_id, self.pricing_month)
        subscription.action_confirm()
        subscription._recompute_prices()
        invoice = subscription._create_invoices()
        invoice._post()
        self.assertEqual(invoice.amount_total, 46)
        # partial refund
        refund_wizard = self.env['account.move.reversal'].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).create({
            'reason': 'Test refund',
            'journal_id': invoice.journal_id.id,
        })
        res = refund_wizard.reverse_moves()
        refund_move = self.env['account.move'].browse(res['res_id'])
        refund_move.invoice_line_ids.quantity = 1
        refund_move._post()
        self.assertEqual(refund_move.amount_total, 23, "The refund is half the invoice")

        url = self._build_url("/my/subscriptions/%s/transaction/" % subscription.id)
        data = {'access_token': subscription.access_token,
                'landing_route': subscription.get_portal_url(),
                'provider_id': self.dummy_provider.id,
                'payment_method_id': self.payment_method_id,
                'token_id': False,
                'flow': 'direct',
                }
        self.make_jsonrpc_request(url, data)
        invoice_transactions = subscription.invoice_ids.transaction_ids
        # the amount should be equal to the last
        self.assertEqual(invoice_transactions.amount, subscription.amount_total,
                         "The last transaction should be equal to the total")

    def test_portal_partial_payment(self):
        with patch('odoo.addons.sale_subscription.models.sale_order.SaleOrder._do_payment',
                   wraps=self._mock_subscription_do_payment):
            self.env['ir.config_parameter'].sudo().set_param('sale.automatic_invoice', 'False')
            with freeze_time("2024-01-22"):
                subscription = self.subscription.create({
                    'partner_id': self.partner.id,
                    'company_id': self.company.id,
                    'sale_order_template_id': self.subscription_tmpl.id,
                })
                self.pricing_month.price = 100
                subscription._onchange_sale_order_template_id()
                subscription.state = 'sent'
                subscription._portal_ensure_token()
                # test customized /payment/pay route with sale_order_id param
                # partial amount specified
                subscription.prepayment_percent = 0.5
                self.amount = subscription.amount_total / 2.0 # self.amount is used to create the right transaction
                with MockRequest(self.env):
                    tx_context = CustomerPortal()._get_payment_values(
                        subscription, is_down_payment=True, payment_amount=self.amount
                    )
                tx_route_values = {
                    'provider_id': self.provider.id,
                    'payment_method_id': self.payment_method_id,
                    'token_id': None,
                    'amount': tx_context['amount'],
                    'flow': 'direct',
                    'tokenization_requested': False,
                    'landing_route': '/my/subscriptions',
                    'access_token': tx_context['access_token'],
                }
                with mute_logger('odoo.addons.payment.models.payment_transaction'):
                    processing_values = self._get_processing_values(
                        tx_route=tx_context['transaction_route'], **tx_route_values
                    )
                tx_sudo = self._get_tx(processing_values['reference'])
                # make sure to have a token on the transaction. it is needed to test the confirmation flow
                tx_sudo.token_id = self.payment_token.id
                self.assertEqual(tx_sudo.sale_order_ids, subscription)
                # self.assertEqual(tx_sudo.amount, amount)
                self.assertEqual(tx_sudo.sale_order_ids.transaction_ids, tx_sudo)

                tx_sudo._set_done()
                with mute_logger('odoo.addons.sale.models.payment_transaction'):
                    tx_sudo._post_process()
                self.assertEqual(subscription.state, 'sale')  # The prepayment amount was paid
                self.assertEqual(subscription.next_invoice_date, datetime.date.today())
                self.assertEqual(subscription.state, 'sale')
                self.assertEqual(subscription.invoice_count, 0, "No invoice should be created")
                self.assertFalse(subscription.payment_token_id, "No token should be saved")

                # Renew subscription and set payment amount as half of the total amount (partial).
                subscription._create_recurring_invoice()
                action = subscription.prepare_renewal_order()
                renewal_so = self.env['sale.order'].browse(action['res_id'])
                renewal_so.prepayment_percent = 0.5
                self.amount = renewal_so.amount_total / 2.0

                # Prepare renewal subscription's payment values.
                with MockRequest(self.env):
                    tx_context = CustomerPortal()._get_payment_values(
                        renewal_so, is_down_payment=True, payment_amount=self.amount
                    )
                tx_route_values = {
                    'provider_id': self.provider.id,
                    'payment_method_id': self.payment_method_id,
                    'token_id': None,
                    'amount': tx_context['amount'],
                    'flow': 'direct',
                    'tokenization_requested': False,
                    'landing_route': '/my/subscriptions',
                    'access_token': tx_context['access_token'],
                }
                with mute_logger('odoo.addons.payment.models.payment_transaction'):
                    processing_values = self._get_processing_values(tx_route=tx_context['transaction_route'], **tx_route_values)

                # Make sure to have a token on the transaction, it is needed to test the confirmation flow.
                tx_sudo = self._get_tx(processing_values['reference'])
                tx_sudo.token_id = self.payment_token.id
                self.assertEqual(tx_sudo.sale_order_ids, renewal_so)
                self.assertEqual(tx_sudo.sale_order_ids.transaction_ids, tx_sudo)
                tx_sudo._set_done()
                with mute_logger('odoo.addons.sale.models.payment_transaction'):
                    tx_sudo._post_process()

                # Assert that no token was saved, renewal was sent and only one invoice was registered.
                self.assertFalse(renewal_so.payment_token_id, "No token should be saved")
                self.assertEqual(renewal_so.state, 'sale')  # The prepayment amount was paid
                self.assertEqual(renewal_so.invoice_count, 1, "Only one invoice from previous subscription should be registered")
                self.assertEqual(renewal_so.next_invoice_date, datetime.date.today() + datetime.timedelta(days=31))

    def test_portal_payment_confirmation_email(self):
        """Check that payment confirmation emails aren't sent for validation transactions."""
        def process_notification_data(data):
            tx = self.env['payment.transaction'].search(
                [('reference', '=', data['reference'])],
                limit=1,
            )
            tx.token_id = tx.tokenize and self.env['payment.token'].create({
                'partner_id': self.subscription.partner_id.id,
                'payment_method_id': self.payment_method_id,
                'provider_id': self.provider.id,
                'provider_ref': 'test123',
            })
            tx._set_done()

        self.portal_user.email = 'chell@aperture.com'
        self.subscription.partner_id = self.portal_partner
        self.subscription.action_confirm()

        subscription_tx_url = f'/my/subscriptions/{self.subscription.id}/transaction'
        base_tx_route_values = {
            'access_token': None,
            'amount': 0.0,
            'flow': 'direct',
            'is_validation': False,
            'landing_route': self.subscription.get_portal_url(),
            'order_id': self.subscription.id,
            'payment_method_id': self.payment_method_id,
            'provider_id': self.provider.id,
            'token_id': None,
            'tokenization_requested': False,
        }

        with patch.object(SaleOrder, '_send_order_notification_mail') as notification_mail_mock:
            # Log in and save a payment method for a subscription
            self.authenticate(self.portal_user.login, self.portal_user.login)
            tx_response = self.make_jsonrpc_request(subscription_tx_url, {
                **base_tx_route_values,
                'is_validation': True,
                'tokenization_requested': True,
            })
            process_notification_data(tx_response)
            self.make_jsonrpc_request('/payment/status/poll', {})
            self.assertFalse(
                notification_mail_mock.call_count,
                "Setting a payment token shouldn't send a payment succeeded email",
            )

            # Use saved payment method to pay subscription
            tx_response = self.make_jsonrpc_request(subscription_tx_url, {
                **base_tx_route_values,
                'amount': self.subscription.amount_total,
                'flow': 'token',
                'token_id': self.subscription.payment_token_id.id,
            })
            process_notification_data(tx_response)
            self.make_jsonrpc_request('/payment/status/poll', {})
            self.assertEqual(
                notification_mail_mock.call_count,
                1,
                "Paying a subscription should send one payment succeeded email",
            )

    def test_portal_quote_document(self):
        product_document = self.env['product.document'].create({
            'name': 'doc.txt',
            'active': True,
            'datas': 'TXkgYXR0YWNobWVudA==',
            'res_model': 'product.product',
            'res_id': self.sub_product_tmpl.product_variant_ids.id,
            'attached_on_sale': 'sale_order',
        })
        self.subscription.action_confirm()
        response = self.url_open(
            self.subscription.get_portal_url('/document/' + str(product_document.id))
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual("My attachment", response.text)

    def test_save_token_automating_future_payments(self):
        with patch('odoo.addons.sale_subscription.models.sale_order.SaleOrder._do_payment',
                   wraps=self._mock_subscription_do_payment):
            # Create subscription and invoice.
            subscription = self.subscription.create({
                'partner_id': self.partner.id,
                'company_id': self.company.id,
                'sale_order_template_id': self.subscription_tmpl.id,
            })
            self.pricing_month.price = 100
            subscription._onchange_sale_order_template_id()
            subscription.action_confirm()
            invoice = subscription._create_recurring_invoice()
            # Define test payment token for later assignment.
            test_payment_token = self.env['payment.token'].create({
                'payment_details': 'Test',
                'partner_id': subscription.partner_id.id,
                'provider_id': self.dummy_provider.id,
                'payment_method_id': self.payment_method_id,
                'provider_ref': 'test'
            })
            # Create transaction and process payment while assigning token to subscription.
            tx_context = self._get_payment_context(self._make_http_get_request(
                f'/my/subscriptions/{subscription.id}',
                params={'access_token': subscription.access_token},
            ))
            tx_route_values = {
                'provider_id': self.provider.id,
                'payment_method_id': self.payment_method_id,
                'token_id': test_payment_token.id,
                'amount': tx_context['amount'],
                'flow': 'token',
                'tokenization_requested': 'automate_payments',
                'landing_route': '/my/invoices/%s' % invoice.id,
                'access_token': tx_context['access_token'],
            }
            with mute_logger('odoo.addons.payment.models.payment_transaction'):
                processing_values = self._get_processing_values(tx_route=tx_context['transaction_route'], **tx_route_values)
            tx_sudo = self._get_tx(processing_values['reference'])
            tx_sudo._set_done()
            with mute_logger('odoo.addons.sale.models.payment_transaction'):
                tx_sudo._post_process()
            # Ensure token was assigned after completing the payment in invoices route.
            self.assertEqual(subscription.payment_token_id.id, test_payment_token.id, "Token must be assigned to subscription after transaction creation.")
            # Create transaction with new token without sending invoice_ids in custom_create_values.
            test_payment_token_2 = self.env['payment.token'].create({
                'payment_details': 'Test-2',
                'partner_id': subscription.partner_id.id,
                'provider_id': self.dummy_provider.id,
                'payment_method_id': self.payment_method_id,
                'provider_ref': 'test-2'
            })
            kwargs = {
                'provider_id': self.provider.id,
                'payment_method_id': self.payment_method_id,
                'token_id': test_payment_token_2.id,
                'amount': tx_context['amount'],
                'flow': 'token',
                'landing_route': '/my/invoices/%s' % invoice.id,
                'currency_id': subscription.currency_id.id,
                'partner_id': self.partner.id
            }
            tx_sudo = self._create_transaction(**kwargs)
            tx_sudo._post_process()
            tx_sudo._set_done()
            # Ensure token was not changed after completing the payment in invoices route.
            self.assertEqual(subscription.payment_token_id.id, test_payment_token.id, "Token must remain unchanged after new payment.")

    def test_anticipate_period(self):
        """ When the payment is performed on subscription, we always create a new invoice
        """
        subscription = self.subscription.create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'payment_token_id': self.payment_token.id,
            'sale_order_template_id': self.subscription_tmpl.id,

        })
        subscription._onchange_sale_order_template_id()
        subscription.order_line.price_unit = 10
        subscription.action_confirm()
        inv1 = subscription._create_invoices()
        inv1._post()  # we won't pay it
        existing_tx = subscription.transaction_ids
        data = {'access_token': subscription.access_token,
                'landing_route': subscription.get_portal_url(),
                'provider_id': self.dummy_provider.id,
                'payment_method_id': self.payment_method_id,
                'token_id': False,
                'amount': subscription.amount_total,
                'flow': 'direct',
                'subscription_anticipate': True
        }
        url = self._build_url("/my/subscriptions/%s/transaction" % subscription.id)
        self.make_jsonrpc_request(url, data)
        self.assertEqual(subscription.invoice_count, 1, "Portal don't create new invoices")
        self.assertEqual(inv1.payment_state, 'not_paid', "inv 1 is not paid")
        tx = subscription.transaction_ids - existing_tx
        tx._set_done()
        tx._post_process()
        inv2 = subscription.invoice_ids - inv1
        self.env['account.payment.register'] \
                .with_context(active_model='account.move', active_ids=inv2.ids) \
                .create({
                'currency_id': subscription.currency_id.id,
                'amount': subscription.amount_total,
        })._create_payments()
        tx = subscription.transaction_ids.invoice_ids.transaction_ids
        tx._set_done()
        tx._post_process()
        self.assertTrue(inv2.payment_state in ['paid', 'in_payment'], "invoice 2  is paid")

    def test_controller_reopen_subscription(self):
        """ When the payment is performed on subscription, we always create a new invoice
        """
        with freeze_time('2024-01-01'):
            subscription = self.subscription.create({
                'partner_id': self.partner.id,
                'company_id': self.company.id,
                'payment_token_id': self.payment_token.id,
                'sale_order_template_id': self.subscription_tmpl.id,

            })
            subscription._onchange_sale_order_template_id()
            subscription.order_line.price_unit = 10
            subscription.action_confirm()
            inv1 = subscription._create_invoices()
            inv1.button_cancel()

        with freeze_time('2024-01-15'):
            subscription.set_close()
            existing_tx = subscription.transaction_ids
            data = {'access_token': subscription.access_token,
                    'landing_route': subscription.get_portal_url(),
                    'provider_id': self.dummy_provider.id,
                    'payment_method_id': self.payment_method_id,
                    'token_id': False,
                    'amount': subscription.amount_total,
                    'flow': 'direct',
                    'subscription_anticipate': True
            }
            url = self._build_url("/my/subscriptions/%s/transaction" % subscription.id)
            self.make_jsonrpc_request(url, data)
            new_tx = subscription.transaction_ids - existing_tx
            new_tx._set_done()
            new_tx._post_process()
            self.assertEqual(subscription.invoice_count, 2, "subscription_anticipate should for a new invoice creation")
            inv2 = subscription.invoice_ids - inv1
            self.env['account.payment.register'] \
                    .with_context(active_model='account.move', active_ids=inv2.ids) \
                    .create({
                    'currency_id': subscription.currency_id.id,
                    'amount': subscription.amount_total,
            })._create_payments()
            tx = subscription.transaction_ids.invoice_ids.transaction_ids
            tx._set_done()
            tx._post_process()
            self.assertTrue(inv2.payment_state in ['paid', 'in_payment'], "invoice 2  is paid")
            self.assertEqual(subscription.next_invoice_date, datetime.date(2024, 2, 1))
            self.assertEqual(inv2.line_ids.mapped(lambda aml: (aml.deferred_start_date, aml.deferred_end_date)),
                             [(datetime.date(2024, 1, 1), datetime.date(2024, 1, 31)),
                                (datetime.date(2024, 1, 1), datetime.date(2024, 1, 31)),
                                (False, False),
                                (False, False)],
                             )

    def test_close_at_date_contract(self):
        """
        Test the closing of a subscription at a specific date.
        """
        with freeze_time("2021-11-17"):
            self.authenticate(None, None)
            self.subscription.plan_id.user_closable = True
            self.subscription.plan_id.user_closable_options = "at_date"
            self.subscription.action_confirm()
            inv1 = self.subscription._create_invoices()
            inv1._post()  # We won't pay it

        with freeze_time("2021-11-18"):
            close_reason_id = self.env.ref("sale_subscription.close_reason_1")
            data = {
                "access_token": self.subscription.access_token,
                "csrf_token": http.Request.csrf_token(self),
                "close_reason_id": close_reason_id.id,
                "closing_text": "I am not able to continue subs"
            }
            url = f"/my/subscriptions/{self.subscription.id}/close"
            res = self.url_open(url, allow_redirects=False, data=data)
            self.assertEqual(res.status_code, 303, "Redirection status code should be 303.")
            self.env.invalidate_all()
            self.env["sale.order"].sudo()._cron_subscription_expiration()
            self.assertEqual(
                self.subscription.subscription_state, "6_churn",
                "Subscription state should be '6_churn'."
            )
            self.assertEqual(
                self.subscription.end_date, date(2021, 11, 18),
                "End date should be the closing date: 2021-11-18."
            )
            self.assertTrue(
                self.subscription.close_reason_id,
                "Close reason should be set after closing."
            )

    def test_close_end_of_period_contract(self):
        """
        Test the closing of a subscription at the end of the period.
        """
        with freeze_time("2021-11-17"):
            self.authenticate(None, None)
            self.subscription.plan_id.user_closable = True
            self.subscription.plan_id.user_closable_options = "end_of_period"
            self.subscription.action_confirm()
            inv1 = self.subscription._create_invoices()
            inv1._post()  # We won't pay it

        with freeze_time("2021-11-18"):
            close_reason_id = self.env.ref("sale_subscription.close_reason_1")
            data = {
                "access_token": self.subscription.access_token,
                "csrf_token": http.Request.csrf_token(self),
                "close_reason_id": close_reason_id.id,
                "closing_text": "I am not able to continue subs"
            }
            url = f"/my/subscriptions/{self.subscription.id}/close"
            res = self.url_open(url, allow_redirects=False, data=data)
            self.assertEqual(res.status_code, 303, "Redirection status code should be 303.")
            self.env.invalidate_all()
            self.assertEqual(self.subscription.subscription_state, "3_progress", "Subscription should still be in progress.")
            self.assertEqual(
                self.subscription.next_invoice_date - relativedelta(days=1), self.subscription.end_date,
                "End date should be one day before next invoice date."
            )

        with freeze_time("2021-12-17"):
            self.env["sale.order"].sudo()._cron_subscription_expiration()
            self.assertEqual(
                self.subscription.subscription_state, "6_churn",
                "Subscription state should be '6_churn' after closing."
            )
            self.assertTrue(self.subscription.close_reason_id, "Close reason should be set after closing.")

    def test_check_product_catalog_data(self):
        """
        Test that creating a sale order with both subscription and normal products
        reflects the correct pricing in the catalog and sale order lines.
        """
        sub_product = self.env['product.product'].create({
            'name': 'Subscription Product',
            'type': 'service',
            'recurring_invoice': True,
            'invoice_policy': 'order',
            'list_price': 100.0,
        })
        non_sub_product = self.env['product.product'].create({
            'name': 'Non-Subscription Product',
            'type': 'service',
            'invoice_policy': 'order',
            'list_price': 50.0,
        })
        sale_order = self.env['sale.order'].create({
            'name': 'Test Sale Order',
            'partner_id': self.partner.id,
            'plan_id': self.plan_month.id,
        })
        data = {
            "id": 0,
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                'res_model': 'sale.order',
                'order_id': sale_order.id,
                'product_ids': [sub_product.id, non_sub_product.id],
            }
        }
        headers = {
            "Content-Type": "application/json",
        }
        self.authenticate(self.env.user.login, self.env.user.login)

        # Make the request
        response = self.url_open(
            '/product/catalog/order_lines_info',
            data=json.dumps(data).encode(),
            headers=headers
        )

        # Check the response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        response_prices = {
            int(product_id): product_data['price']
            for product_id, product_data in response_data['result'].items()
        }
        expected_prices = {
            sub_product.id: sub_product.list_price,
            non_sub_product.id: non_sub_product.list_price,
        }
        # Ensure both are sorted before comparison
        self.assertEqual(
            sorted(response_prices.items()),
            sorted(expected_prices.items()),
            "Prices in the response should match the expected list prices."
        )

    def test_modification_of_subscription_addresses(self):
        """
        Tests that the invoicng address linked to a subscription can be updated from the portal.
        """
        fpos_1 = self.env['account.fiscal.position'].create({
            'name': "Test fpos 1",
            'country_id': self.env.ref('base.be').id,
            'foreign_vat': 'BE0477472701',
        })
        self.portal_user.property_account_position_id = fpos_1.id
        invoicing_partner = self.env['res.partner'].create({
            'name': 'John Doe',
            'street': "Example street 13",
            'street2': "",
            'city': "Example city",
            'zip': 1234,
            'state_id': False,
            'country_id': self.env.ref('base.be').id,
            'property_account_position_id': fpos_1.id,
            'type': 'invoice',
            'commercial_partner_id': self.portal_user.partner_id.commercial_partner_id.id,
        })
        shipping_partner_1 = self.env['res.partner'].create({
            'name': 'John Doe',
            'street': "Example street 13",
            'street2': "",
            'city': "Example city",
            'zip': 1234,
            'state_id': False,
            'country_id': self.env.ref('base.be').id,
            'property_account_position_id': fpos_1.id,
            'type': 'delivery',
            'commercial_partner_id': self.portal_user.partner_id.commercial_partner_id.id,
        })
        self.portal_user.child_ids = [Command.link(invoicing_partner.id)]
        self.subscription.partner_id = self.portal_partner
        self.subscription.user_id.group_ids += self.env.ref('account.group_delivery_invoice_address')
        self.subscription.action_confirm()
        original_shipping_partner = self.subscription.partner_shipping_id
        # Update the partner
        self.authenticate(self.portal_user.login, self.portal_user.login)
        data = {
            "csrf_token": http.Request.csrf_token(self),
            "access_token": self.subscription.access_token,
            "delivery_address": shipping_partner_1.id,
            "invoicing_address": invoicing_partner.id,
        }
        url = f"/my/subscriptions/{self.subscription.id}/change_address"
        res = self.url_open(url, allow_redirects=False, data=data)
        self.assertEqual(res.status_code, 303, "Redirection status code should be 303.")
        self.subscription.invalidate_recordset(fnames=['partner_shipping_id', 'partner_invoice_id'])
        self.assertEqual(self.subscription.partner_shipping_id, original_shipping_partner, "shipping partner is not updated even when it is provided")
        self.assertEqual(self.subscription.partner_invoice_id, invoicing_partner, "the invoicing partner is updated")

    def test_portal_user_sees_company_subscriptions(self):
        """Test that a portal user sees all subscriptions of their company and not others."""
        company = self.env['res.partner'].create({
            'name': 'Test Company',
            'is_company': True,
        })
        self.user.partner_id.parent_id = company.id
        self.other_user.partner_id.parent_id = company.id

        self.subscription._onchange_sale_order_template_id()
        self.subscription.action_confirm()

        # Create a subscription for an external unrelated partner
        external_partner = self.env['res.partner'].create({'name': 'External Partner'})
        external_subscription = self.subscription.copy({
            'partner_id': external_partner.id,
        })
        external_subscription._onchange_sale_order_template_id()
        external_subscription.action_confirm()

        # First, remove all existing group memberships from self.user to avoid conflicts with exclusive groups
        # Then, explicitly assign the Portal group to self.user to simulate portal-level access
        portal_group = self.env.ref('base.group_portal')
        self.user.write({
            'group_ids': [Command.clear(), Command.link(portal_group.id)]
        })

        # Authenticate as self.user and access the subscriptions page
        self.authenticate(self.user.login, self.user.password)
        response = self.url_open('/my/subscriptions')
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        self.assertIn(self.subscription.name, content, "Portal user should see subscriptions from their company")
        self.assertNotIn(external_subscription.name, content, "Portal user should NOT see subscriptions from other companies")

    def test_subscription_pause(self):
        """ Test pausing a subscription from the portal and verifying its effects. """
        with freeze_time("2021-11-17"):
            self.authenticate(None, None)
            self.subscription.plan_id.pausable_by_user = True
            self.subscription.action_confirm()
            self.subscription._create_invoices()._post()

        with freeze_time("2021-11-18"):
            pause_until = self.subscription.next_invoice_date + relativedelta(days=2)
            user_lang = get_lang(self.env)
            date_format = user_lang.date_format
            pause_until_str = pause_until.strftime(date_format)
            response = self._pause_subscription(pause_until_str)

            self.assertEqual(response.status_code, 303, "Expected redirection status code 303.")
            self.env.invalidate_all()
            self.assertEqual(self.subscription.subscription_state, "3_progress", "Subscription should remain in progress.")
            self.assertEqual(self.subscription.next_invoice_date, pause_until, "Next invoice date should be extended by 2 days.")

        with freeze_time("2021-12-19"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(self.subscription.invoice_count, 2, "Invoice count should be 2.")
            self.assertEqual(self.subscription.next_invoice_date, datetime.date(2022, 1, 19), "Next invoice date should be updated correctly.")

    def test_subscription_pause_and_resume(self):
        """ Test pausing and then resuming a subscription from the portal. """
        with freeze_time("2021-11-17"):
            self.authenticate(None, None)
            self.subscription.plan_id.pausable_by_user = True
            self.subscription.action_confirm()
            self.subscription._create_invoices()._post()

        with freeze_time("2021-11-18"):
            pause_until = self.subscription.next_invoice_date + relativedelta(days=3)
            user_lang = get_lang(self.env)
            date_format = user_lang.date_format
            pause_until_str = pause_until.strftime(date_format)
            response = self._pause_subscription(pause_until_str)

            self.assertEqual(response.status_code, 303, "Expected redirection status code 303.")
            self.env.invalidate_all()
            self.assertEqual(self.subscription.subscription_state, "3_progress", "Subscription should remain in progress.")
            self.assertEqual(self.subscription.next_invoice_date, pause_until, "Next invoice date should be extended by 3 days.")

        with freeze_time("2021-12-18"):
            response = self._resume_subscription()

            self.assertEqual(response.status_code, 303, "Expected redirection status code 303.")
            self.env.invalidate_all()
            self.assertEqual(self.subscription.next_invoice_date, datetime.date(2021, 12, 18), "Next invoice date should reset correctly.")

            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(self.subscription.next_invoice_date, datetime.date(2022, 1, 18), "Next invoice date should update after invoicing.")

    def test_reset_pause_period_after_invoice_creation(self):
        """ Test that the pause period is reset after an invoice is created. """
        with freeze_time("2021-11-17"):
            self.authenticate(None, None)
            self.subscription.plan_id.pausable_by_user = True
            self.subscription.action_confirm()
            self.subscription._create_invoices()._post()

        with freeze_time("2021-11-18"):
            pause_until = self.subscription.next_invoice_date + relativedelta(days=10)
            user_lang = get_lang(self.env)
            date_format = user_lang.date_format
            pause_until_str = pause_until.strftime(date_format)
            response = self._pause_subscription(pause_until_str)

            self.assertEqual(response.status_code, 303, "Expected redirection status code 303.")
            self.env.invalidate_all()
            self.assertEqual(self.subscription.subscription_state, "3_progress", "Subscription should remain in progress.")

        with freeze_time("2021-12-19"):
            # By creating a manual invoice, we reset the user_pause_start
            self.subscription._create_invoices()._post()
            self.assertEqual(self.subscription.invoice_count, 2, "Invoice count should be 2.")
            self.assertFalse(self.subscription.user_pause_start, "User pause start should be reset after invoicing.")
