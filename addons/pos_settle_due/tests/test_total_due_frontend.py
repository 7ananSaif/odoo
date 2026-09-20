# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.point_of_sale.models.pos_config import PosConfig
from unittest.mock import patch
from odoo import Command


@odoo.tests.tagged('post_install', '-at_install')
class TestPointOfSaleFlow(TestPointOfSaleHttpCommon):

    def test_settle_account_due_update_instantly(self):
        self.partner_test_a = self.env["res.partner"].create({"name": "A Partner"})
        self.customer_account_payment_method = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'split_transactions': True,
        })

        self.main_pos_config.write({'payment_method_ids': [(4, self.customer_account_payment_method.id)]})
        self.main_pos_config.open_ui()
        self.start_tour("/pos/ui/%d" % self.main_pos_config.id, 'pos_settle_account_due_update_instantly', login="accountman")

    def test_settle_order_partially_backend(self):
        """
        - Create an invoice when paying an order with customer account from POS, pay partially the invoice from PoS and go to backend to check that the amount residual is decreased.
        - Then pay partially from the backend, and check that the amount due is updated in the POS.
        """
        self.partner_test_a = self.env["res.partner"].create({"name": "A Partner"})
        self.customer_account_payment_method = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'split_transactions': True,
        })

        self.main_pos_config.write({'payment_method_ids': [(4, self.customer_account_payment_method.id)]})
        self.main_pos_config.open_ui()
        self.start_tour("/pos/ui?config_id=%d" % self.main_pos_config.id, 'test_settle_order_partially_backend_01', login="accountman")
        self.main_pos_config.current_session_id.close_session_from_ui()

        pos_invoice = self.partner_test_a.invoice_ids[0]
        self.assertEqual(pos_invoice.amount_residual, 9.8)
        self.env['account.payment.register'].with_context(active_ids=pos_invoice.ids, active_model='account.move').create({
            'payment_date': pos_invoice.date,
            'amount': 5,
        })._create_payments()
        self.assertEqual(pos_invoice.amount_residual, 4.8)

        self.main_pos_config.open_ui()
        self.start_tour("/pos/ui?config_id=%d" % self.main_pos_config.id, 'test_settle_order_partially_backend_02', login="accountman")
        self.main_pos_config.current_session_id.close_session_from_ui()
        self.assertEqual(pos_invoice.amount_residual, 0)
        self.assertEqual(self.partner_test_a.total_due, 0)

    def test_settle_due_account_button(self):
        """ Test that an invoice can be created after the session is closed """
        self.customer_account_payment_method = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'split_transactions': True,
        })
        self.partner_test_a = self.env["res.partner"].create({"name": "A Partner"})
        self.partner_test_b = self.env["res.partner"].create({"name": "B Partner"})

        self.main_pos_config.write({'payment_method_ids': [(4, self.customer_account_payment_method.id)]})

        self.main_pos_config.open_ui()
        current_session = self.main_pos_config.current_session_id

        order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': current_session.id,
            'partner_id': self.partner_test_b.id,
            'lines': [(0, 0, {
                'name': "OL/0001",
                'product_id': self.product_a.id,
                'price_unit': 1000,
                'discount': 0,
                'qty': 1,
                'tax_ids': [[6, False, []]],
                'price_subtotal': 1000,
                'price_subtotal_incl': 1000,
            })],
            'pricelist_id': self.main_pos_config.pricelist_id.id,
            'amount_paid': 1000.0,
            'amount_total': 1000.0,
            'amount_tax': 0.0,
            'amount_return': 0.0,
        })

        payment_context = {"active_ids": order.ids, "active_id": order.id}
        order_payment = self.env['pos.make.payment'].with_context(**payment_context).create({
            'amount': 1000.0,
            'payment_method_id': self.customer_account_payment_method.id
        })
        order_payment.with_context(**payment_context).check()
        current_session.close_session_from_ui()
        self.main_pos_config.open_ui()
        self.start_tour("/pos/ui/%d" % self.main_pos_config.id, 'SettleDueButtonPresent', login="accountman")

        self.main_pos_config.current_session_id.close_session_from_ui()
        self.main_pos_config.write({'payment_method_ids': [(3, self.customer_account_payment_method.id)]})
        self.main_pos_config.open_ui()
        self.start_tour("/pos/ui?config_id=%d" % self.main_pos_config.id, 'test_settle_due_account_ui_coherency_2', login="accountman")

    def test_settle_due_search_more(self):
        self.customer_account_payment_method = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'split_transactions': True,
        })
        partner_test_a = self.env["res.partner"].create({"name": "APartner"})
        partner_test_b = self.env["res.partner"].create({"name": "BPartner"})

        def mocked_get_limited_partners_loading(self, offset=0):
            return [(partner_test_a.id,)]

        payment_methods = self.main_pos_config.payment_method_ids | self.customer_account_payment_method
        self.main_pos_config.write({'payment_method_ids': [Command.set(payment_methods.ids)]})

        self.assertEqual(partner_test_b.total_due, 0)
        self.assertEqual(partner_test_b.has_moves, False)

        self.main_pos_config.with_user(self.pos_admin).open_ui()
        current_session = self.main_pos_config.current_session_id

        order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': current_session.id,
            'partner_id': partner_test_b.id,
            'lines': [Command.create({
                'product_id': self.product_a.id,
                'price_unit': 10,
                'discount': 0,
                'qty': 1,
                'price_subtotal': 10,
                'price_subtotal_incl': 10,
            })],
            'amount_paid': 10.0,
            'amount_total': 10.0,
            'amount_tax': 0.0,
            'amount_return': 0.0,
            'to_invoice': True,
            'last_order_preparation_change': '{}'
        })

        payment_context = {"active_ids": order.ids, "active_id": order.id}
        order_payment = self.env['pos.make.payment'].with_context(**payment_context).create({
            'amount': 10.0,
            'payment_method_id': self.customer_account_payment_method.id
        })
        order_payment.with_context(**payment_context).check()

        self.assertEqual(partner_test_b.total_due, 10)
        current_session.action_pos_session_closing_control()
        self.assertEqual(partner_test_b.has_moves, True)

        self.main_pos_config.with_user(self.user).open_ui()
        with patch.object(PosConfig, 'get_limited_partners_loading', mocked_get_limited_partners_loading):
            self.main_pos_config.open_ui()
            self.start_tour("/pos/ui/%d" % self.main_pos_config.id, 'SettleDueAmountMoreCustomers', login="pos_user")
