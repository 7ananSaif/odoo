# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests.common import tagged
from odoo.tests import Form

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged('post_install', '-at_install')
class TestPoSRental(TestPointOfSaleHttpCommon):
    def test_rental_with_lots(self):
        """ Test rental product with lots """
        self.tracked_product_id = self.env['product.product'].create({
            'name': 'Test2',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'available_in_pos': True,
            'rent_ok': True,
            'is_storable': True,
            'tracking': 'serial',
        })

        # Set Stock quantities

        self.lot_id1 = self.env['stock.lot'].create({
            'product_id': self.tracked_product_id.id,
            'name': "123456789",
        })
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        quants = self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.tracked_product_id.id,
            'inventory_quantity': 1.0,
            'lot_id': self.lot_id1.id,
            'location_id': warehouse.lot_stock_id.id,
        })
        quants.action_apply_inventory()

        self.cust1 = self.env['res.partner'].create({
            'name': 'test_rental_1',
            'street': 'street',
            'city': 'city',
            'country_id': self.env.ref('base.be').id, })

        self.sale_order_id = self.env['sale.order'].with_context(in_rental_app=True).sudo().create({
            'partner_id': self.cust1.id,
            'partner_invoice_id': self.cust1.id,
            'partner_shipping_id': self.cust1.id,
            'rental_start_date': fields.Datetime.today(),
            'rental_return_date': fields.Datetime.today() + timedelta(days=3),
            'order_line': [
                Command.create({
                    'product_id': self.tracked_product_id.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 250,
                })
            ]
        })

        self.pos_user.write({
            'group_ids': [
                (4, self.env.ref('stock.group_stock_manager').id),
                (4, self.env.ref('sales_team.group_sale_manager').id),
                (4, self.env.ref('account.group_account_user').id),
                (4, self.env.ref('base.group_system').id),  # You are not allowed to access 'Test Inherit Daughter' (test_inherit_daughter) records.
            ]
        })
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("OrderLotsRentalTour", login="pos_user")
        self.main_pos_config.current_session_id.action_pos_session_closing_control()
        self.assertEqual(self.sale_order_id.order_line.pickedup_lot_ids.name, '123456789')

    def test_rental_qty_delivered(self):
        """ Test rental product qty delivered when processed in PoS """
        self.env.user.write({
            'group_ids': [
                Command.link(self.ref('sale_stock_renting.group_rental_stock_picking')),
            ]
        })
        self.env['res.config.settings'].create({'group_rental_stock_picking': False}).execute()
        self.env['res.config.settings'].create({'group_rental_stock_picking': True}).execute()
        self.test_product = self.env['product.product'].create({
            'name': 'Test Rental',
            'available_in_pos': True,
            'rent_ok': True,
            'is_storable': True,
        })

        self.test_product_non_rental = self.env['product.product'].create({
            'name': 'Test Non Rental',
            'available_in_pos': True,
            'is_storable': True,
        })

        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        self.env['stock.quant']._update_available_quantity(self.test_product, warehouse.lot_stock_id, 10.0)

        self.pricelist = self.env['product.pricelist'].create({
            'name': 'Test Pricelist',
        })

        self.sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.partner_full.id,
            'partner_invoice_id': self.partner_full.id,
            'partner_shipping_id': self.partner_full.id,
            'rental_start_date': fields.Datetime.today(),
            'rental_return_date': fields.Datetime.today() + timedelta(days=3),
        })

        self.order_line = self.env['sale.order.line'].sudo().create({
            'order_id': self.sale_order.id,
            'product_id': self.test_product.id,
            'product_uom_qty': 1.0
        })

        self.order_line_non_rental = self.env['sale.order.line'].sudo().create({
            'order_id': self.sale_order.id,
            'product_id': self.test_product_non_rental.id,
            'product_uom_qty': 1.0,
        })

        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.order_line.update({'is_rental': True})
        pos_order = {'amount_paid': 20,
           'amount_return': 0,
           'amount_tax': 0,
           'amount_total': 20,
           'date_order': fields.Datetime.to_string(fields.Datetime.now()),
           'fiscal_position_id': False,
           'to_invoice': True,
           'partner_id': self.partner_full.id,
           'pricelist_id': self.pricelist.id,
           'lines': [[0,
             0,
             {'discount': 0,
              'pack_lot_ids': [],
              'price_unit': 10,
              'product_id': self.test_product.id,
              'price_subtotal': 10,
              'price_subtotal_incl': 10,
              'sale_order_line_id': self.order_line.id,
              'sale_order_origin_id': self.sale_order.id,
              'qty': 1,
              'tax_ids': []}], [0,
             0,
             {'discount': 0,
              'pack_lot_ids': [],
              'price_unit': 10,
              'product_id': self.test_product_non_rental.id,
              'price_subtotal': 10,
              'price_subtotal_incl': 10,
              'sale_order_line_id': self.order_line_non_rental.id,
              'sale_order_origin_id': self.sale_order.id,
              'qty': 1,
              'tax_ids': []}]],
           'name': 'Order 00044-003-0014',
           'session_id': self.main_pos_config.current_session_id.id,
           'sequence_number': self.main_pos_config.journal_id.id,
           'payment_ids': [[0,
             0,
             {'amount': 20,
              'name': fields.Datetime.now(),
              'payment_method_id': self.main_pos_config.payment_method_ids[0].id}]],
           'uuid': '00044-003-0014',
           'user_id': self.env.uid}

        self.env['pos.order'].sync_from_ui([pos_order])

        self.assertEqual(self.order_line.qty_delivered, 1.0)
        self.assertEqual(self.order_line_non_rental.qty_delivered, 1.0)
        return_action = self.sale_order.action_open_return()
        wizard = Form(self.env['rental.order.wizard'].sudo().with_context(return_action['context'])).save()
        wizard.apply()

        self.assertEqual(self.order_line.qty_delivered, 1.0)
        self.assertEqual(self.order_line.qty_returned, 1.0)

    def test_rental_qty_delivered_without_rental_picking(self):
        """ Test rental product qty delivered when processed in PoS when rental picking is disabled """
        test_product = self.env['product.product'].create({
            'name': 'Rental',
            'rent_ok': True,
            'is_storable': True,
        })

        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.partner_full.id,
            'partner_invoice_id': self.partner_full.id,
            'partner_shipping_id': self.partner_full.id,
            'rental_start_date': fields.Datetime.today(),
            'rental_return_date': fields.Datetime.today() + timedelta(days=3),
            'order_line': [Command.create({
                'product_id': test_product.id,
                'product_uom_qty': 1.0,
                'is_rental': True,
            })],
        })

        self.main_pos_config.with_user(self.pos_user).open_ui()

        pos_order = {'amount_paid': 1,
           'amount_return': 0,
           'amount_tax': 0,
           'amount_total': 1,
           'date_order': fields.Datetime.to_string(fields.Datetime.now()),
           'fiscal_position_id': False,
           'to_invoice': True,
           'partner_id': self.partner_full.id,
           'pricelist_id': False,
           'lines': [[0,
             0,
             {'discount': 0,
              'pack_lot_ids': [],
              'price_unit': 1,
              'product_id': test_product.id,
              'price_subtotal': 1,
              'price_subtotal_incl': 1,
              'sale_order_line_id': sale_order.order_line.id,
              'sale_order_origin_id': sale_order.id,
              'qty': 1,
              'tax_ids': []}]],
           'name': 'Order 00022-001-0001',
           'session_id': self.main_pos_config.current_session_id.id,
           'sequence_number': 1,
           'payment_ids': [[0,
             0,
             {'amount': 1,
              'name': fields.Datetime.now(),
              'payment_method_id': self.main_pos_config.payment_method_ids[0].id}]],
           'uuid': '00022-001-0001',
           'user_id': self.env.uid}

        self.env['pos.order'].sync_from_ui([pos_order])

        self.assertEqual(sale_order.order_line.qty_delivered, 1.0)
        return_action = sale_order.action_open_return()
        wizard = Form(self.env['rental.order.wizard'].sudo().with_context(return_action['context'])).save()
        wizard.apply()

        self.assertEqual(sale_order.order_line.qty_delivered, 1.0)
        self.assertEqual(sale_order.order_line.qty_returned, 1.0)
