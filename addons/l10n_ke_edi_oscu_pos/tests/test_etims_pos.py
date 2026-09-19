from odoo.addons.l10n_ke_edi_oscu_pos.tests.common import CommonPosKeEdiTest
from odoo.addons.l10n_ke_edi_oscu.tests.common import TestKeEdiCommon
from odoo.addons.l10n_ke_edi_oscu.tests.test_live import TestKeEdi
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEtimsPos(TestKeEdiCommon, CommonPosKeEdiTest):
    @classmethod
    @TestKeEdi.setup_country('ke')
    def setUpClass(self):
        super().setUpClass()
        self.company.l10n_ke_server_mode = 'demo'

    def test_etims_post_order(self):
        """Testing the pos order process to make sure everything is correctly sends to eTIMS
        """
        order, _ = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_moda.id
            },
            'line_data': [
                {'product_id': self.twenty_dollars_with_10_incl.product_variant_id.id}
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id}
            ]
        })

        order.action_post_order()
        self.assertEqual(order.l10n_ke_oscu_internal_data, 'GRKJVWYCFBPTYQ225X2UEYONVE')
        self.assertEqual(order.l10n_ke_oscu_signature, '123456789ODOOGR3')
        self.assertEqual(order.l10n_ke_oscu_receipt_number, 169)

        # Send stock move to eTIMS
        with self.enter_registry_test_mode():
            self.env.ref('l10n_ke_edi_oscu_stock.ir_cron_send_stock_moves').method_direct_trigger()
        self.assertEqual(order.picking_ids.l10n_ke_oscu_sar_number, 1)

    def test_invoice_order(self):
        order, _ = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_moda.id,
                'to_invoice': True,
            },
            'line_data': [
                {'product_id': self.twenty_dollars_with_10_incl.product_variant_id.id}
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id}
            ]
        })

        order.action_post_order()

        # As the etims call is send in the pos order, we just copy the values from pos order to invoice
        # to avoid duplicate calls
        self.assertEqual(order.l10n_ke_oscu_internal_data, order.account_move.l10n_ke_oscu_internal_data)
        self.assertEqual(order.l10n_ke_oscu_signature, order.account_move.l10n_ke_oscu_signature)
        self.assertEqual(order.l10n_ke_oscu_receipt_number, order.account_move.l10n_ke_oscu_receipt_number)

    def test_cant_send_order_with_product_out_of_stock(self):
        order, _ = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_moda.id,
            },
            'line_data': [
                {'product_id': self.twenty_dollars_with_10_incl.product_variant_id.id, 'qty': 100}
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id}
            ]
        })

        # Send order to eTIMS, should raise an error
        with self.assertRaises(UserError):
            order.action_post_order()

    def test_refund_pos_order(self):
        _, refund = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_moda.id,
                'to_invoice': True,
            },
            'line_data': [
                {'product_id': self.twenty_dollars_with_10_incl.product_variant_id.id}
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id}
            ],
            'refund_data': [
                {'payment_method_id': self.cash_payment_method.id}
            ]
        })

        refund.action_post_order()
        self.assertEqual(refund.l10n_ke_oscu_internal_data, 'GRKJVWYCFBPTYQ225X2UEYONVE')
        self.assertEqual(refund.l10n_ke_oscu_signature, '123456789ODOOGR3')
        self.assertEqual(refund.l10n_ke_oscu_receipt_number, 169)
