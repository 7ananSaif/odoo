# Part of Odoo. See LICENSE file for full copyright and licensing details.
from contextlib import contextmanager
from unittest.mock import patch, DEFAULT

from freezegun import freeze_time

from odoo import Command, fields
from odoo.tests.common import tagged
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


class TestSaleSubscriptionExternalCommon:
    @contextmanager
    def patch_set_external_taxes(self, new_set_external_taxes=None):
        def is_computed_externally(self):
            for move in self.filtered(lambda record: record._name == 'account.move'):
                move.is_tax_computed_externally = move.move_type == 'out_invoice'

            for order in self.filtered(lambda record: record._name == 'sale.order'):
                order.is_tax_computed_externally = True

        # autospec to capture self in call_args_list (https://docs.python.org/3/library/unittest.mock-examples.html#mocking-unbound-methods)
        # patch out the _post because _create_recurring_invoice will auto-post the invoice which will also trigger tax computation, that's not what this test is about
        target = new_set_external_taxes or DEFAULT
        with patch('odoo.addons.account_external_tax.models.account_external_tax_mixin.AccountExternalTaxMixin._set_external_taxes', target, autospec=target == DEFAULT) as mocked_set, \
             patch('odoo.addons.account_external_tax.models.account_external_tax_mixin.AccountExternalTaxMixin._compute_is_tax_computed_externally', is_computed_externally):
            yield mocked_set


@tagged("-at_install", "post_install")
class TestSaleSubscriptionExternal(TestSubscriptionCommon, TestSaleSubscriptionExternalCommon):
    def test_01_subscription_external_taxes_called(self):
        self.subscription.action_confirm()

        with self.patch_set_external_taxes() as mocked_set:
            invoice = self.subscription.with_context(auto_commit=False)._create_recurring_invoice()

        self.assertIn(
            invoice,
            [args[0] for args, kwargs in mocked_set.call_args_list],
            'Should have queried external taxes on the new invoice.'
        )

    def test_02_subscription_do_payment(self):
        invoice_values = self.subscription._prepare_invoice()
        new_invoice = self.env["account.move"].create(invoice_values)

        payment_method = self.env['payment.token'].create({
            'payment_details': 'Jimmy McNulty',
            'partner_id': self.subscription.partner_id.id,
            'provider_id': self.provider.id,
            'payment_method_id': self.payment_method_id,
            'provider_ref': 'Omar Little'
        })

        with self.patch_set_external_taxes() as mocked_set:
            self.subscription._do_payment(payment_method, new_invoice)

        self.assertIn(
            new_invoice,
            [args[0] for args, kwargs in mocked_set.call_args_list],
            'Should have queried external taxes on the new invoice.'
        )

    def test_03_subscription_fully_paid(self):
        sub = self.subscription
        self.assertGreater(sub.amount_tax, 0, 'Subscription should have taxes so this test can test what happens when Avatax overrides it.')
        sub.action_confirm()

        def new_set_external_taxes(self, mapped_taxes):
            """Simulate what happens for an exempt sale order: amounts that don't match the set tax."""
            sub.order_line.write({
                'tax_ids': [Command.clear()]
            })

        # Calculate initial taxes
        with self.patch_set_external_taxes(new_set_external_taxes):
            sub.button_external_tax_calculation()

        tx = self.env['payment.transaction'].sudo().create({
            'payment_method_id': self.payment_method_id,
            'amount': sub.amount_total,
            'currency_id': sub.currency_id.id,
            'provider_id': self.provider.id,
            'reference': 'test',
            'operation': 'online_redirect',
            'partner_id': self.partner.id,
            'sale_order_ids': sub.ids,
            'state': 'done',
        })
        self.provider.journal_id.inbound_payment_method_line_ids |= self.env["account.payment.method.line"].sudo().create({
            'payment_method_id': self.env["account.payment.method"].sudo().create({
                'name': 'test',
                'payment_type': 'inbound',
                'code': 'none',
            }).id,
        })
        self.env.invalidate_all()

        with self.patch_set_external_taxes(new_set_external_taxes):
            tx._post_process()

        self.assertEqual(sub.amount_total, sub.invoice_ids[0].amount_paid, 'Subscription should be fully paid')

    def test_04_subscription_date(self):
        self.subscription.date_order = '2024-01-01'
        self.assertFalse(self.subscription.next_invoice_date, "Shouldn't have a next invoice date for this test.")

        today = '2024-02-02'
        with freeze_time(today):
            self.assertEqual(
                self.subscription._get_external_tax_service_params()['document_date'],
                fields.Date.from_string(today),
                'The current date should be sent for subscriptions.'
            )

    def test_05_recurring_total_match(self):
        sub = self.subscription
        sub.is_tax_computed_externally = True

        sub.order_line = sub.order_line.filtered(lambda x: x.recurring_invoice)

        def new_set_external_taxes(self, mapped_taxes):
            """Simulate what happens for an exempt sale order: amounts that don't match the set tax."""
            for line in sub.order_line:
                line.price_subtotal = line.price_unit * line.product_uom_qty * 0.5
                line.price_tax = line.price_unit * line.product_uom_qty * 0.5
                line.price_total = line.price_subtotal + line.price_tax

        with self.patch_set_external_taxes(new_set_external_taxes):
            sub.button_external_tax_calculation()

        self.assertEqual(sub.recurring_total, sub.amount_untaxed)
