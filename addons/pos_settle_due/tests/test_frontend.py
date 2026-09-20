import odoo
from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon

@odoo.tests.tagged('post_install', '-at_install')
class TestPoSSettleDueHttpCommon(TestPointOfSaleHttpCommon, TestPoSCommon):

    def test_pos_reconcile(self):
        # create customer account payment method
        self.customer_account_payment_method = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'split_transactions': True,
        })
        # add customer account payment method to pos config
        self.main_pos_config.write({
            'payment_method_ids': [(4, self.customer_account_payment_method.id, 0)],
        })

        self.assertEqual(self.partner_test_1.total_due, 0)

        self.main_pos_config.with_user(self.pos_admin).open_ui()
        current_session = self.main_pos_config.current_session_id

        order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': current_session.id,
            'partner_id': self.partner_test_1.id,
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

        self.make_payment(order, self.customer_account_payment_method, 10.0)

        self.assertEqual(self.partner_test_1.total_due, 10)
        current_session.action_pos_session_closing_control()

        self.main_pos_config.settle_due_product_id = self.env.ref("pos_settle_due.product_product_settle")
        self.main_pos_config.with_user(self.user).open_ui()
        self.start_tour("/pos/ui/%d" % self.main_pos_config.id, 'pos_settle_account_due', login="accountman")
        self.main_pos_config.current_session_id.action_pos_session_closing_control()
        self.assertEqual(self.partner_test_1.total_due, 0)

    def test_settle_open_invoice(self):
        """ Test to settle an open invoice from PoS """
        self.user.group_ids = [Command.unlink(self.env.ref('base.group_system').id)]
        self.partner_c = self.env["res.partner"].create({"name": "C Partner"})
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_c.id,
            'date': '2025-02-17',
            'invoice_date': '2025-02-17',
            'move_type': 'out_invoice',
            'invoice_line_ids': [
                (0, 0, {'name': 'test', 'price_unit': 200})
            ],
        })
        invoice.action_post()
        self.assertEqual(self.partner_c.total_due, 200)

        self.customer_account_payment_method = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'split_transactions': True,
        })
        self.main_pos_config.write({
            'payment_method_ids': [(4, self.customer_account_payment_method.id, 0)],
        })
        self.main_pos_config.settle_invoice_product_id = self.env.ref("pos_settle_due.product_product_settle_invoice")
        self.main_pos_config.open_ui()
        self.start_tour("/pos/ui/%d" % self.main_pos_config.id, 'pos_settle_open_invoice', login="accountman")
        self.main_pos_config.current_session_id.action_pos_session_closing_control()
        self.assertEqual(self.partner_c.total_due, 195)

    def test_settle_open_invoice_with_credit_note(self):
        """Ensure POS settles net amount of invoice minus credit note via 'Settle invoices'."""
        self.partner_c = self.env["res.partner"].create({"name": "C Partner"})

        invoice = self.env["account.move"].create({
            "partner_id": self.partner_c.id,
            "date": "2025-02-17",
            "invoice_date": "2025-02-17",
            "move_type": "out_invoice",
            "invoice_line_ids": [(0, 0, {"name": "test", "price_unit": 10})],
        })
        invoice.action_post()
        credit_note = self.env["account.move"].create({
            "partner_id": self.partner_c.id,
            "date": "2025-02-17",
            "invoice_date": "2025-02-17",
            "move_type": "out_refund",
            "invoice_line_ids": [(0, 0, {"name": "credit", "price_unit": 2})],
        })
        credit_note.action_post()

        self.assertEqual(self.partner_c.total_due, 8)

        self.customer_account_payment_method = self.env["pos.payment.method"].create({
            "name": "Customer Account",
            "split_transactions": True,
        })
        self.main_pos_config.write({
            "payment_method_ids": [(4, self.customer_account_payment_method.id, 0)],
        })
        self.main_pos_config.settle_invoice_product_id = self.env.ref(
            "pos_settle_due.product_product_settle_invoice"
        )

        self.main_pos_config.open_ui()
        self.start_tour(
            "/pos/ui?config_id=%d" % self.main_pos_config.id,
            "pos_settle_open_invoice_with_credit_note",
            login="accountman",
        )
        self.main_pos_config.current_session_id.action_pos_session_closing_control()
        self.assertEqual(self.partner_c.total_due, 0)
