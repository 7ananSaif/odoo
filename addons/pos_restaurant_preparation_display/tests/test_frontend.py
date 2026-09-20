# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.pos_restaurant.tests import test_frontend
from odoo.addons.pos_enterprise.tests.test_frontend import TestPreparationDisplayHttpCommon
from unittest.mock import patch
import odoo.tests
import json


@odoo.tests.tagged('post_install', '-at_install')
class TestUi(test_frontend.TestFrontendCommon, TestPreparationDisplayHttpCommon):
    def test_01_preparation_display_resto(self):
        self.pdis.write({
            'pos_config_ids': [(4, self.pos_config.id)],
        })

        # open a session, the /pos/ui controller will redirect to it
        self.pos_config.printer_ids.unlink()
        self.pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('PreparationDisplayTourResto')

        self.start_pdis_tour('PreparationDisplayFrontEndCancelTour')

        # Order 1 should have 2 preparation orderlines (Coca-Cola and Water)
        order1 = self.env['pos.order'].search([('pos_reference', 'ilike', '%-000001')], limit=1)
        pdis_order1 = self.env['pos.prep.order'].search([('pos_order_id', '=', order1.id)], limit=1)
        self.assertEqual(len(pdis_order1.prep_line_ids), 2, "Should have 2 preparation orderlines")

        # Order 2 should have 1 preparation orderline (Coca-Cola)
        order2 = self.env['pos.order'].search([('pos_reference', 'ilike', '%-000002')], limit=1)
        pdis_order2 = self.env['pos.prep.order'].search([('pos_order_id', '=', order2.id)], limit=1)
        self.assertEqual(len(pdis_order2.prep_line_ids), 1, "Should have 1 preparation orderline")
        self.assertEqual(pdis_order2.prep_line_ids.quantity, 1, "Should have 1 quantity of Coca-Cola")

        # Order 3 should have 3 preparation orderlines (Coca-Cola, Water and Minute Maid)
        # with one cancelled Minute Maid
        order3 = self.env['pos.order'].search([('pos_reference', 'ilike', '%-000003')], limit=1)
        pdis_order3 = self.env['pos.prep.order'].search([('pos_order_id', '=', order3.id)], limit=1)
        cancelled_orderline = pdis_order3.prep_line_ids.filtered(lambda x: x.product_id.name == 'Minute Maid')
        self.assertEqual(cancelled_orderline.cancelled, 1, "Should have 1 cancelled Minute Maid orderline")
        self.assertEqual(cancelled_orderline.product_id.name, 'Minute Maid', "Cancelled orderline should be Minute Maid")

    def test_02_preparation_display_resto(self):
        self.pdis.write({
            'pos_config_ids': [(4, self.pos_config.id)],
        })

        # open a session, the /pos/ui controller will redirect to it
        self.pos_config.printer_ids.unlink()
        self.pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('PreparationDisplayTourResto2')

        # Order 1 should have 1 preparation orderlines (Coca-Cola) with quantity 2
        order1 = self.env['pos.order'].search([('pos_reference', 'ilike', '%-000001')], limit=1)
        prep_line = self.env['pos.prep.line'].search([
            ('prep_order_id.pos_order_id', '=', order1.id),
        ])
        self.assertEqual(len(prep_line), 2)
        self.assertEqual(sum(prep_line.mapped('quantity')), 2)

    def test_preparation_display_with_internal_note(self):
        self.pdis.write({
            'pos_config_ids': [(4, self.pos_config.id)],
        })
        self.pos_config.printer_ids.unlink()
        self.pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('PreparationDisplayTourInternalNotes')

        self.start_pdis_tour('PreparationDisplayFrontEndNoteTour')

        # Order 1 should have 2 preparation orderlines (Coca-Cola and Water)
        order1 = self.env['pos.order'].search([('pos_reference', 'ilike', '%-000001')], limit=1)
        pdis_order1 = self.env['pos.prep.order'].search([('pos_order_id', '=', order1.id)])
        self.assertEqual(len(pdis_order1.prep_line_ids), 2, "Should have 2 preparation orderlines")
        self.assertEqual(pdis_order1.prep_line_ids[0].quantity, 1)
        self.assertEqual(json.loads(pdis_order1.prep_line_ids[0].internal_note)[0]['text'], "Test Internal Notes")
        self.assertEqual(pdis_order1.prep_line_ids[1].quantity, 1)
        self.assertEqual(pdis_order1.prep_line_ids[1].internal_note, "[]")

    def test_cancel_order_notifies_display(self):
        category = self.env['pos.category'].create({'name': 'Food'})
        self.env['product.product'].create({
            'name': 'Test Food',
            'list_price': 10,
            'taxes_id': False,
            'available_in_pos': True,
            'pos_categ_ids': category,
        })
        self.pdis.write({
            'pos_config_ids': [(4, self.pos_config.id)],
            'category_ids': category,
        })

        notifications = []

        def _send_load_orders_message(self, sound, notification, orderId):
            notifications.append(self.id)

        # open a session, the /pos/ui controller will redirect to it
        with patch('odoo.addons.pos_enterprise.models.pos_prep_display.PosPrepDisplay._send_load_orders_message', new=_send_load_orders_message):
            self.pos_config.printer_ids.unlink()
            self.pos_config.with_user(self.pos_user).open_ui()
            self.start_pos_tour('PreparationDisplayCancelOrderTour')

        # Should receive 2 notifications, 1 placing the order, 1 cancelling it
        self.assertEqual(notifications.count(self.pdis.id), 2)

    def test_payment_does_not_cancel_display_orders(self):
        self.pdis.write({
            'pos_config_ids': [(4, self.pos_config.id)],
        })
        self.pos_config.printer_ids.unlink()
        self.pos_config.with_user(self.pos_user).open_ui()
        self.start_tour("/pos/ui/%d" % self.main_pos_config.id, 'PreparationDisplayPaymentNotCancelDisplayTour', login="pos_user")
        pos_order = self.env['pos.order'].search([], limit=1)
        pdis_order = self.env['pos.prep.order'].search(
            [('pos_order_id', '=', pos_order.id)]
        )
        pdis_lines = pdis_order.prep_line_ids
        self.assertEqual(len(pdis_lines), 2)
        self.assertEqual(pdis_lines[0].quantity, 2.0)
        self.assertEqual(pdis_lines[0].cancelled, 1.0)
        self.assertEqual(pdis_lines[1].quantity, 2.0)
        self.assertEqual(pdis_lines[1].cancelled, 0.0)

    def test_update_internal_note_of_order(self):
        category = self.env['pos.category'].create({'name': 'Test-cat'})
        product_1, product_2 = self.env['product.product'].create([{
            'name': 'Test Food',
            'list_price': 10,
            'taxes_id': False,
            'available_in_pos': True,
            'pos_categ_ids': category,
        }, {
            'name': 'Demo Food',
            'list_price': 10,
            'taxes_id': False,
            'available_in_pos': True,
            'pos_categ_ids': category,
        }])

        self.env['pos.prep.display'].create({
            'name': 'Preparation Display (Food only)',
            'pos_config_ids': [(4, self.pos_config.id)],
            'category_ids': category,
        })

        self.pos_config.with_user(self.pos_admin).open_ui()
        self.start_tour("/pos/ui?config_id=%d" % self.pos_config.id, 'test_update_internal_note_of_order', login='pos_admin')

        pos_order = self.env['pos.order'].search([('session_id', 'in', self.pos_config.session_ids.ids)], limit=1)
        order_lines = self.env['pos.prep.order'].search([('pos_order_id', '=', pos_order.id)], limit=1).prep_line_ids
        self.assertEqual(len(order_lines), 2)
        self.assertEqual(pos_order.state, 'paid')
        self.assertEqual(pos_order.amount_paid, product_2.list_price)

        self.assertEqual(order_lines[0]['product_id'].id, product_2.id)
        self.assertEqual(order_lines[0]['quantity'], 1)
        self.assertEqual(order_lines[0]['cancelled'], 0)

        self.assertEqual(order_lines[1]['product_id'].id, product_1.id)
        self.assertEqual(order_lines[1]['internal_note'], '[]')
        self.assertEqual(order_lines[1]['quantity'], 1)
        self.assertEqual(order_lines[1]['cancelled'], 1)

    def test_receipt_screen_after_unsent_order_dialog(self):
        self.env['pos.prep.display'].create({
            'name': 'Preparation Display',
            'pos_config_ids': [(4, self.pos_config.id)],
        })
        self.pos_config.printer_ids.unlink()
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('test_receipt_screen_after_unsent_order_dialog')
        order = self.env['pos.order'].search([('pos_reference', 'ilike', '%-000001')], limit=1)
        pdis_order = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)], limit=1)
        self.assertEqual(len(pdis_order.prep_line_ids), 1, "Should have 1 preparation orderline")
        self.assertEqual(pdis_order.prep_line_ids.quantity, 1, "Should have 1 quantity of Coca-Cola")

    def test_order_preparation(self):
        self.env['pos.prep.display'].create({
            'name': 'Preparation Display (Food only)',
            'pos_config_ids': [(4, self.pos_config.id)],
        })

        self.pos_config.write({'module_pos_restaurant': False})
        self.pos_config.with_user(self.pos_admin).open_ui()
        self.start_tour("/pos/ui?config_id=%d" % self.pos_config.id, 'test_order_preparation_preparation_printer', login='pos_admin')

        current_session = self.pos_config.current_session_id
        current_session.post_closing_cash_details(0)
        current_session.close_session_from_ui()
        self.pos_config.write({'printer_ids': [], 'is_order_printer': False, 'module_pos_restaurant': True})
        self.pos_config.with_user(self.pos_admin).open_ui()
        self.start_tour("/pos/ui?config_id=%d" % self.pos_config.id, 'test_order_preparation_preparation_display', login='pos_admin')
        last_orders = self.pos_config.current_session_id.order_ids

        first_order = last_orders[1]
        preparation_change = self.env['pos.prep.order'].search([('pos_order_id', '=', first_order.id)])
        product_quantity = preparation_change.prep_line_ids.mapped('quantity')
        product_cancelled = preparation_change.prep_line_ids.mapped('cancelled')
        self.assertEqual(product_cancelled, product_quantity, "A one-time order must be successfully cancelled.")

        second_order = last_orders[0]
        preparation_change = self.env['pos.prep.order'].search([('pos_order_id', '=', second_order.id)])
        product_quantity = preparation_change.prep_line_ids.mapped('quantity')
        product_cancelled = preparation_change.prep_line_ids.mapped('cancelled')
        self.assertEqual(product_cancelled, product_quantity, "A two-times order must be successfully cancelled")

    def setup_table_actions(self):
        drinks_category = self.env['pos.category'].search([('name', '=', 'Drinks')], limit=1)
        self.env['pos.prep.display'].create({
            'name': 'Preparation Display (Drinks only)',
            'pos_config_ids': [(4, self.pos_config.id)],
            'category_ids': [(4, drinks_category.id)],
        })

        self.fanta = self.env['product.product'].create({
            'available_in_pos': True,
            'list_price': 2.00,
            'name': 'Fanta',
            'weight': 0.01,
            'pos_categ_ids': [(4, drinks_category.id)],
            'taxes_id': [(6, 0, [])],
        })
        self.espresso = self.env['product.product'].create({
            'available_in_pos': True,
            'list_price': 3.00,
            'name': 'Espresso',
            'weight': 0.01,
            'pos_categ_ids': [(4, drinks_category.id)],
            'taxes_id': [(6, 0, [])],
        })
        self.cocktail = self.env['product.product'].create({
            'available_in_pos': True,
            'list_price': 5.00,
            'name': 'Cocktail',
            'weight': 0.01,
            'pos_categ_ids': [(4, drinks_category.id)],
            'taxes_id': [(6, 0, [])],
        })
        self.beer = self.env['product.product'].create({
            'available_in_pos': True,
            'list_price': 2.50,
            'name': 'Beer',
            'weight': 0.01,
            'pos_categ_ids': [(4, drinks_category.id)],
            'taxes_id': [(6, 0, [])],
        })
        self.champagne = self.env['product.product'].create({
            'available_in_pos': True,
            'list_price': 10.00,
            'name': 'Champagne',
            'weight': 0.01,
            'pos_categ_ids': [(4, drinks_category.id)],
            'taxes_id': [(6, 0, [])],
        })

    def _assert_pdis_order(self, pdis_order, triples):
        for product_name, quantity, cancelled in triples:
            prep_line = pdis_order.prep_line_ids.filtered(lambda prep_line: prep_line.product_id.name == product_name and prep_line.quantity == quantity and prep_line.cancelled == cancelled)
            self.assertEqual(len(prep_line), 1)

    def test_table_actions_transfer(self):
        self.setup_table_actions()
        self.pos_config.printer_ids.unlink()
        self.pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('table_action_transfer')

        pos_order = self.env['pos.order'].search([('pos_reference', 'ilike', '%-000001')])
        pdis_orders = self.env['pos.prep.order'].search([('pos_order_id', '=', pos_order.id)]).sorted('id')

        self.assertEqual(len(pos_order), 1)
        self.assertEqual(len(pos_order.lines), 4)
        self.assertTrue(all(line.qty == 3 for line in pos_order.lines))

        self.assertEqual(len(pdis_orders), 3)
        self._assert_pdis_order(pdis_orders[0], [
            ("Coca-Cola", 3, 3),
            ("Water", 3, 3),
            ("Minute Maid", 3, 3),
            ("Fanta", 3, 3),
        ])
        self._assert_pdis_order(pdis_orders[1], [
            ("Minute Maid", 5, 2),
            ("Fanta", 5, 2),
        ])
        self._assert_pdis_order(pdis_orders[2], [
            ("Coca-Cola", 5, 2),
            ("Water", 5, 2),
        ])

    def test_table_actions_merge(self):
        self.setup_table_actions()
        self.pos_config.printer_ids.unlink()
        self.pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('table_action_merge')

        pos_order = self.env['pos.order'].search([('pos_reference', 'ilike', '%-000001')])
        pdis_orders = self.env['pos.prep.order'].search([('pos_order_id', '=', pos_order.id)]).sorted('id')

        self.assertEqual(len(pos_order), 1)
        self.assertEqual(len(pos_order.lines), 8)
        self.assertTrue(all(line.qty == 3 for line in pos_order.lines))

        self.assertEqual(len(pdis_orders), 5)
        self._assert_pdis_order(pdis_orders[0], [
            ("Coca-Cola", 3, 3),
            ("Water", 3, 3),
            ("Minute Maid", 3, 3),
            ("Fanta", 3, 3),
        ])
        self._assert_pdis_order(pdis_orders[1], [
            ("Minute Maid", 5, 2),
            ("Fanta", 5, 2),
        ])
        self._assert_pdis_order(pdis_orders[2], [
            ("Espresso", 3, 3),
            ("Cocktail", 3, 3),
            ("Beer", 3, 3),
            ("Champagne", 3, 3),
        ])
        self._assert_pdis_order(pdis_orders[3], [
            ("Beer", 5, 2),
            ("Champagne", 5, 2),
        ])
        self._assert_pdis_order(pdis_orders[4], [
            ("Coca-Cola", 5, 2),
            ("Water", 5, 2),
            ("Espresso", 5, 2),
            ("Cocktail", 5, 2),
        ])

    def test_table_actions_link(self):
        self.setup_table_actions()
        self.pos_config.printer_ids.unlink()
        self.pos_config.with_user(self.pos_admin).open_ui()
        self.start_pos_tour('table_action_link', login='pos_admin')

        pos_order = self.env['pos.order'].search([('pos_reference', 'ilike', '%-000001')])
        pdis_orders = self.env['pos.prep.order'].search([('pos_order_id', '=', pos_order.id)]).sorted('id')

        self.assertEqual(len(pos_order), 1)
        self.assertEqual(len(pos_order.lines), 8)
        self.assertTrue(all(qty == 3.0 for qty in pos_order.lines.mapped("qty")))

        self.assertEqual(len(pdis_orders), 5)
        self._assert_pdis_order(pdis_orders[0], [
            ("Coca-Cola", 3, 3),
            ("Water", 3, 3),
            ("Minute Maid", 3, 3),
            ("Fanta", 3, 3),
        ])
        self._assert_pdis_order(pdis_orders[1], [
            ("Minute Maid", 5, 2),
            ("Fanta", 5, 2),
        ])
        self._assert_pdis_order(pdis_orders[2], [
            ("Espresso", 3, 3),
            ("Cocktail", 3, 3),
            ("Beer", 3, 3),
            ("Champagne", 3, 3),
        ])
        self._assert_pdis_order(pdis_orders[3], [
            ("Beer", 5, 2),
            ("Champagne", 5, 2),
        ])
        self._assert_pdis_order(pdis_orders[4], [
            ("Coca-Cola", 5, 2),
            ("Water", 5, 2),
            ("Espresso", 5, 2),
            ("Cocktail", 5, 2),
        ])

    def test_table_actions_unlink(self):
        self.setup_table_actions()
        self.pos_config.printer_ids.unlink()
        self.pos_config.with_user(self.pos_admin).open_ui()
        self.start_pos_tour('table_action_unlink', login='pos_admin')

        last_orders = self.env['pos.order'].search([], limit=3, order='id desc')
        pos_order_1 = last_orders[2]
        pos_order_2 = last_orders[0]
        pdis_orders_1 = self.env['pos.prep.order'].search([('pos_order_id', '=', pos_order_1.id)]).sorted('id')
        pdis_orders_2 = self.env['pos.prep.order'].search([('pos_order_id', '=', pos_order_2.id)]).sorted('id')

        self.assertEqual(len(pos_order_1), 1)
        self.assertEqual(len(pos_order_1.lines), 6)
        self.assertEqual(sorted(pos_order_1.lines.mapped('qty')), [0.0, 1.0, 2.0, 3.0, 3.0, 5.0])

        self.assertEqual(len(pos_order_2), 1)
        self.assertEqual(len(pos_order_2.lines), 4)
        self.assertEqual(sorted(pos_order_2.lines.mapped('qty')), [1.0, 1.0, 3.0, 5.0])

        self.assertEqual(len(pdis_orders_1), 4)
        self._assert_pdis_order(pdis_orders_1[0], [
            ("Coca-Cola", 3, 3),
            ("Water", 3, 3),
            ("Minute Maid", 3, 3),
            ("Fanta", 3, 3),
        ])
        self._assert_pdis_order(pdis_orders_1[1], [
            ("Minute Maid", 5, 2),
            ("Fanta", 5, 2),
        ])
        self._assert_pdis_order(pdis_orders_1[2], [
            ("Coca-Cola", 5, 2),
            ("Water", 5, 5),
            ("Espresso", 5, 5),
            ("Cocktail", 5, 3),
        ])
        self._assert_pdis_order(pdis_orders_1[3], [
            ("Coca-Cola", 2, 0),
            ("Water", 2, 1),
        ])

        self.assertEqual(len(pdis_orders_2), 3)
        self._assert_pdis_order(pdis_orders_2[0], [
            ("Espresso", 3, 3),
            ("Cocktail", 3, 3),
            ("Beer", 3, 3),
            ("Champagne", 3, 3),
        ])
        self._assert_pdis_order(pdis_orders_2[1], [
            ("Beer", 5, 2),
            ("Champagne", 5, 5),
        ])
        self._assert_pdis_order(pdis_orders_2[2], [
            ("Espresso", 5, 0),
            ("Cocktail", 1, 0),
            ("Champagne", 2, 1),
        ])
