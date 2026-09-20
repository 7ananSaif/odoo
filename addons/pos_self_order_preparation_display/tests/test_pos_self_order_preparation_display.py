# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests
from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


@odoo.tests.tagged('post_install', '-at_install')
class TestPosSelfOrderPreparationDisplay(SelfOrderCommonTest):

    def test_ensure_kiosk_order_preparation_display(self):
        """
        This test ensures that the kiosk order is sent to the preparation display, even if unpaid
        """
        self.pos_config.write({
            'self_ordering_mode': 'kiosk',
            'self_ordering_pay_after': 'each',
            'self_ordering_service_mode': 'table',
        })

        self.env['pos.prep.display'].create({
            'name': 'Preparation Display',
            'pos_config_ids': [(4, self.pos_config.id)],
            'category_ids': [(4, self.cola.pos_categ_ids[0].id)],
        })

        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")

        self_route = self.pos_config._get_self_order_route()
        self.start_tour(self_route, 'self_kiosk_order_preparation_display')

        order = self.env['pos.order'].search([('amount_paid', '=', 0)], limit=1)
        preparation_order = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)], limit=1)
        self.assertEqual(preparation_order.prep_line_ids.product_id, self.cola.product_variant_id)

    def test_ensure_mobile_order_preparation_display(self):
        """
        This test ensures that the mobile order is sent to the preparation display, even if unpaid
        """
        floor = self.env["restaurant.floor"].create({
            "name": 'Main Floor',
            "background_color": 'rgb(249,250,251)',
            "table_ids": [(0, 0, {
                "table_number": 1,
            })],
        })

        self.pos_config.write({
            'self_ordering_mode': 'mobile',
            'self_ordering_pay_after': 'each',
            'self_ordering_service_mode': 'table',
            "floor_ids": [(6, 0, [floor.id])],
        })

        self.env['pos.prep.display'].create({
            'name': 'Preparation Display',
            'pos_config_ids': [(4, self.pos_config.id)],
            'category_ids': [(4, self.cola.pos_categ_ids[0].id)],
        })

        self.env['restaurant.table'].create({
            'table_number': 1234,
            'floor_id': self.pos_config.floor_ids[0].id,
        })

        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")

        self_route = self.pos_config._get_self_order_route(floor.table_ids[0].id)
        with self.assertLogs(level='WARNING') as log_catcher:
            self.start_tour(self_route, 'test_ensure_mobile_order_preparation_display')

        self.assertEqual(len(log_catcher.output), 1, "Exactly one warning should be logged")
        self.assertIn(
            "This order cannot be cancelled because it's already in preparation.",
            log_catcher.output[0],
        )

        order = self.env['pos.order'].search([], limit=1)
        preparation_order = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)], limit=1)
        self.assertEqual(preparation_order.prep_line_ids.product_id, self.cola.product_variant_id)
