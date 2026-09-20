# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests
from odoo.addons.pos_online_payment_self_order.tests.test_self_order_mobile import TestSelfOrderMobile


@odoo.tests.tagged('post_install', '-at_install')
class TestOnlinePaymentPosSelfOrderPrepDisplay(TestSelfOrderMobile):

    def setUp(self):
        super().setUp()
        self.prep_display = self.env['pos.prep.display'].create({
            'name': 'Preparation Display',
            'pos_config_ids': [(4, self.pos_config.id)],
            'category_ids': [(4, self.cola.pos_categ_ids[0].id)],
        })

    def _assert_prep_order_count_before_and_after_payment(self, order, confirmation_page=True):
        """ Check POS order state and related prep order count before and after a valid online payment. """
        prep_order_count = self.env['pos.prep.order'].search_count([('pos_order_id', '=', order.id)])
        self.assertEqual(order.state, "draft")
        self.assertEqual(prep_order_count, 0)

        self._fake_online_payment(order.id, order.access_token, self.payment_provider.id, exit_route="/", confirmation_page=confirmation_page)

        prep_order_count = self.env['pos.prep.order'].search_count([('pos_order_id', '=', order.id)])
        self.assertEqual(order.state, "paid")
        self.assertEqual(prep_order_count, 1)

    def test_ensure_online_kiosk_order_prep_display(self):
        """ This test ensures if online payment is configured, then only paid kiosk order is sent to the prep display """
        self.pos_config.write({
            'use_presets': False,
            'self_ordering_mode': 'kiosk',
            'self_ordering_pay_after': 'each',
            'payment_method_ids': [(4, self.online_payment_method.id)]
        })

        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()

        self.start_tour(self_route, 'test_ensure_online_self_order_prep_display')

        order1 = self.pos_config.current_session_id.order_ids[0]
        self._assert_prep_order_count_before_and_after_payment(order1)

    def test_ensure_online_kiosk_order_prep_display_no_confirmation_page(self):
        self.pos_config.write({
            'use_presets': False,
            'self_ordering_mode': 'kiosk',
            'self_ordering_pay_after': 'each',
            'payment_method_ids': [(4, self.online_payment_method.id)]
        })

        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()

        self.start_tour(self_route, 'test_ensure_online_self_order_prep_display')

        order1 = self.pos_config.current_session_id.order_ids[0]
        self._assert_prep_order_count_before_and_after_payment(order1, confirmation_page=False)

    def test_ensure_online_self_order_prep_display(self):
        """ This test ensures if online payment is configured, then only paid self order is sent to the prep display """
        self.pos_config.write({
            'use_presets': False,
            'self_ordering_mode': 'mobile',
            'self_ordering_pay_after': 'each',
            'self_order_online_payment_method_id': self.online_payment_method.id
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()
        self.start_tour(self_route, 'test_ensure_online_self_order_prep_display')

        order1 = self.pos_config.current_session_id.order_ids[0]
        self._assert_prep_order_count_before_and_after_payment(order1)

    def test_ensure_online_self_order_prep_display_no_confirmation_page(self):
        self.pos_config.write({
            'use_presets': False,
            'self_ordering_mode': 'mobile',
            'self_ordering_pay_after': 'each',
            'self_order_online_payment_method_id': self.online_payment_method.id
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()
        self.start_tour(self_route, 'test_ensure_online_self_order_prep_display')

        order1 = self.pos_config.current_session_id.order_ids[0]
        self._assert_prep_order_count_before_and_after_payment(order1, confirmation_page=False)

    def _assert_prep_order_count_without_payment(self):
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()

        self.start_tour(self_route, 'test_without_online_self_order_prep_display')

        order1 = self.pos_config.current_session_id.order_ids[0]
        prep_order_count = self.env['pos.prep.order'].search_count([('pos_order_id', '=', order1.id)])
        self.assertEqual(order1.state, "draft")
        self.assertEqual(prep_order_count, 1)

    def test_without_online_kiosk_order_prep_display(self):
        self.pos_config.write({
            'use_presets': False,
            'self_ordering_mode': 'kiosk',
            'self_ordering_pay_after': 'each',
        })

        self._assert_prep_order_count_without_payment()

    def test_without_online_self_order_prep_display(self):
        self.pos_config.write({
            'use_presets': False,
            'self_ordering_mode': 'mobile',
            'self_ordering_pay_after': 'each',
        })

        self._assert_prep_order_count_without_payment()
