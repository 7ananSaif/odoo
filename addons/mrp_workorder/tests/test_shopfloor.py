# Part of Odoo. See LICENSE file for full copyright and licensing details.
import unittest

from odoo import Command
from odoo.tests import Form, users
from odoo.tests.common import HttpCase, tagged

@tagged('post_install', '-at_install')
class TestShopFloor(HttpCase):

    def setUp(self):
        super().setUp()
        # Set Administrator as the current user.
        self.uid = self.env.ref('base.user_admin').id
        # Enables Work Order setting, and disables other settings.
        group_workorder = self.env.ref('mrp.group_mrp_routings')
        self.env.user.write({'group_ids': [Command.link(group_workorder.id)]})

        # Create a test dedicated company.
        self.company = self.env['res.company'].create({'name': 'Test ShopFloor Company'})
        self.env.user.company_ids |= self.company
        self.env.user.company_id = self.company
        self.env.company = self.company
        # Create an employee for the user (it will be created for the test company.)
        self.employee = self.env['hr.employee'].create({'user_id': self.env.user.id})

        group_lot = self.env.ref('stock.group_production_lot')
        group_multi_loc = self.env.ref('stock.group_stock_multi_locations')
        group_pack = self.env.ref('stock.group_tracking_lot')
        group_uom = self.env.ref('uom.group_uom')
        self.env.user.write({'group_ids': [Command.unlink(group_lot.id)]})
        self.env.user.write({'group_ids': [Command.unlink(group_multi_loc.id)]})
        self.env.user.write({'group_ids': [Command.unlink(group_pack.id)]})
        # Explicitly remove the UoM group.
        group_user = self.env.ref('base.group_user')
        group_user.write({'implied_ids': [Command.unlink(group_uom.id)]})
        self.env.user.write({'group_ids': [Command.unlink(group_uom.id)]})

        # Add some properties for commonly used in tests records.
        self.warehouse = self.env['stock.warehouse'].create({
            'name': 'Test Warehouse',
            'reception_steps': 'one_step',
            'delivery_steps': 'ship_only',
            'code': 'TWH',
            'sequence': 5,
        })
        # Give WH's manufacturing operation a low sequence to prioritize it over other WH's ones.
        self.warehouse.manu_type_id.sequence = 1
        self.stock_location = self.warehouse.lot_stock_id
        self.test_type_register_production = self.env.ref('mrp_workorder.test_type_register_production')
        # Reset LN/SN sequence for the same reason.
        stock_lot_seq = self.env['ir.sequence'].search([('code', '=', 'stock.lot.serial')])
        stock_lot_seq.number_next_actual = 1

        self.user_without_hr_right = self.env['res.users'].create({
            'name': 'Test without hr right',
            'login': 'test_without_hr_right',
            'group_ids': [
                (6, 0, self.env.user.group_ids.ids),
                Command.unlink(self.env.ref('hr.group_hr_user').id),
                Command.unlink(self.env.ref('hr.group_hr_manager').id),
                Command.unlink(self.env.ref('base.group_system').id),
            ],
        })
        self.user_without_hr_right.action_create_employee()
        employees = self.env['hr.employee'].create([{
            'name': name,
        } for name in ['Abbie Seedy', 'Billy Demo', 'Cory Corrinson']])
        employees[0].barcode = "659898105101"

    def test_shop_floor(self):
        # Creates somme employees for test purpose.

        giraffe = self.env['product.product'].create({
            'name': 'Giraffe',
            'is_storable': True,
            'tracking': 'lot',
        })
        leg = self.env['product.product'].create({
            'name': 'Leg',
            'is_storable': True,
            'barcode': 'PRODUCT_LEG'
        })
        neck = self.env['product.product'].create({
            'name': 'Neck',
            'is_storable': True,
            'tracking': 'serial',
        })
        color = self.env['product.product'].create({
            'name': 'Color',
            'is_storable': True,
        })
        neck_sn_1, neck_sn_2 = self.env['stock.lot'].create([{
            'name': 'NE1',
            'product_id': neck.id,
        }, {
            'name': 'NE2',
            'product_id': neck.id,
        }])
        self.env['stock.quant']._update_available_quantity(leg, self.stock_location, quantity=100)
        self.env['stock.quant']._update_available_quantity(color, self.stock_location, quantity=100)
        self.env['stock.quant']._update_available_quantity(neck, self.stock_location, quantity=1, lot_id=neck_sn_1)
        self.env['stock.quant']._update_available_quantity(neck, self.stock_location, quantity=1, lot_id=neck_sn_2)
        savannah = self.env['mrp.workcenter'].create({
            'name': 'Savannah',
            'time_start': 10,
            'time_stop': 5,
            'time_efficiency': 80,
        })
        jungle = self.env['mrp.workcenter'].create({'name': 'Jungle'})
        bom = self.env['mrp.bom'].create({
            'product_id': giraffe.id,
            'product_tmpl_id': giraffe.product_tmpl_id.id,
            'product_uom_id': giraffe.uom_id.id,
            'product_qty': 1.0,
            'consumption': 'flexible',
            'operation_ids': [
                Command.create({
                'name': 'Creation',
                'workcenter_id': savannah.id,
            }), Command.create({
                'name': 'Release',
                'workcenter_id': jungle.id,
            })],
            'bom_line_ids': [
                Command.create({'product_id': leg.id, 'product_qty': 4}),
                Command.create({'product_id': neck.id, 'product_qty': 1})
            ]
        })
        steps_common_values = {
            'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
            'product_ids': [Command.link(giraffe.id)],
            'operation_id': bom.operation_ids[0].id,
        }
        self.env['quality.point'].create([
            {
                **steps_common_values,
                'title': 'Register Production',
                'test_type_id': self.test_type_register_production.id,
                'sequence': 0,
            },
            {
                **steps_common_values,
                'title': 'Instructions',
                'test_type_id': self.env.ref('quality.test_type_instructions').id,
                'sequence': 1,
                'note': "Create this giraffe with a lot of care !",
            },
            {
                **steps_common_values,
                'title': 'Register legs',
                'component_id': leg.id,
                'test_type_id': self.env.ref('mrp_workorder.test_type_register_consumed_materials').id,
                'sequence': 2,
            },
            {
                **steps_common_values,
                'title': 'Register necks',
                'component_id': neck.id,
                'test_type_id': self.env.ref('mrp_workorder.test_type_register_consumed_materials').id,
                'sequence': 3,
            },
            {
                **steps_common_values,
                'title': 'Release',
                'test_type_id': self.env.ref('quality.test_type_instructions').id,
                'sequence': 4,
            },
        ])
        mo = self.env['mrp.production'].create({
            'product_id': giraffe.id,
            'product_qty': 2,
            'bom_id': bom.id,
        })
        mo.picking_type_id.prefill_shop_floor_lots = True
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()
        self.start_tour('/odoo/shop-floor', "test_shop_floor", login='test_without_hr_right')

        self.assertEqual(mo.move_finished_ids.quantity, 2)
        self.assertRecordValues(mo.move_raw_ids, [
            {'product_id': leg.id, 'quantity': 10.0, 'state': 'done'},
            {'product_id': neck.id, 'quantity': 2.0, 'state': 'done'},
            {'product_id': color.id, 'quantity': 1.0, 'state': 'done'},
        ])
        self.assertRecordValues(mo.workorder_ids, [
            {'state': 'done', 'workcenter_id': savannah.id},
            {'state': 'done', 'workcenter_id': jungle.id},
        ])
        self.assertEqual(mo.workorder_ids[0].finished_lot_ids, mo.move_finished_ids.move_line_ids.lot_id)
        self.assertEqual(mo.workorder_ids[0].qty_produced, 2)
        self.assertEqual(mo.workorder_ids[0].check_ids[2].move_id.quantity, 10)
        self.assertEqual(mo.workorder_ids[0].check_ids[3].move_id.quantity, 2)
        self.assertRecordValues(mo.workorder_ids[0].check_ids[3].move_id.lot_ids, [{'id': neck_sn_1}, {'id': neck_sn_2}])

    @users('test_without_hr_right')
    def test_shop_floor_auto_select_workcenter(self):
        """ This test ensures the right work center is selected when Shop Floor is opened."""
        # Create some products.
        product_final = self.env['product.product'].create({
            'name': 'Pizza',
            'is_storable': True,
        })
        product_comp1 = self.env['product.product'].create({
            'name': 'Pizza dough',
            'is_storable': True,
        })
        product_comp2 = self.env['product.product'].create({
            'name': 'Tomato sauce',
            'is_storable': True,
        })
        # Adds some quantity in stock.
        self.env['stock.quant']._update_available_quantity(product_comp1, self.stock_location, quantity=999)
        self.env['stock.quant']._update_available_quantity(product_comp2, self.stock_location, quantity=999)
        # Create three workcenters.
        wc1, wc2 = self.env['mrp.workcenter'].create([{
            'name': f'Preparation Table {i}',
        } for i in (1, 2)])
        wc1.alternative_workcenter_ids = wc2
        wc2.alternative_workcenter_ids = wc1
        wc3 = self.env['mrp.workcenter'].create({'name': 'Furnace'})
        # Create a BoM.
        bom = self.env['mrp.bom'].create({
            'product_id': product_final.id,
            'product_tmpl_id': product_final.product_tmpl_id.id,
            'product_uom_id': product_final.uom_id.id,
            'product_qty': 1.0,
            'consumption': 'flexible',
            'operation_ids': [
                Command.create({
                'name': 'Prepare the pizza 🤌',
                'workcenter_id': wc1.id,
            }), Command.create({
                'name': 'Bake it!',
                'workcenter_id': wc3.id,
            })],
            'bom_line_ids': [
                Command.create({'product_id': product_comp1.id, 'product_qty': 1}),
                Command.create({'product_id': product_comp2.id, 'product_qty': 1})
            ]
        })
        # Create two Manufacturing Orders.
        all_mo = self.env['mrp.production'].create([{
            'product_id': product_final.id,
            'product_qty': qty,
            'bom_id': bom.id,
        } for qty in (6, 4)])
        all_mo.action_confirm()
        all_mo.action_assign()
        all_mo.button_plan()
        # Mark as done the 2th MO 1st WO.
        all_mo[1].workorder_ids[0].button_start()
        all_mo[1].workorder_ids[0].action_mark_as_done()
        self.start_tour("/odoo/shop-floor", "test_shop_floor_auto_select_workcenter", login='test_without_hr_right')

    @users('test_without_hr_right')
    def test_shop_floor_catalog_add_component_in_two_steps(self):
        """ Ensures when a component is added through the Shop Floor catalog,
        the Pick Component operation is correctly created/updated."""
        # Set the manufacture in 2 steps.
        self.warehouse.manufacture_steps = 'pbm'
        # Create a product with a BoM and two components.
        # Create some products.
        product_final = self.env['product.product'].create({
            'name': 'Pot',
            'is_storable': True,
        })
        product_comp1, product_comp2 = self.env['product.product'].create([{
            'name': 'C1 - Earthenware Clay',
            'is_storable': True,
        }, {
            'name': 'C2 - Stoneware Clay',
            'is_storable': True,
        }])
        bom = self.env['mrp.bom'].create({
            'product_id': product_final.id,
            'product_tmpl_id': product_final.product_tmpl_id.id,
            'product_uom_id': product_final.uom_id.id,
            'product_qty': 1.0,
            'consumption': 'flexible',
            'bom_line_ids': [
                Command.create({'product_id': product_comp1.id, 'product_qty': 1}),
            ]
        })
        # Adds some quantity in stock.
        self.env['stock.quant']._update_available_quantity(product_comp1, self.stock_location, quantity=999)
        self.env['stock.quant']._update_available_quantity(product_comp2, self.stock_location, quantity=999)
        # Create a Manufacturing Order.
        mo = self.env['mrp.production'].create({
            'product_id': product_final.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()
        # Validate the MO's Pick Component.
        self.assertEqual(len(mo.picking_ids), 1)
        mo.picking_ids.button_validate()
        # Simulate "Add Component" from the Shop Floor.
        kwargs = {'from_shop_floor': True}
        mo._update_order_line_info(product_comp2.id, 1, child_field='move_raw_ids', **kwargs)
        self.assertEqual(len(mo.picking_ids), 2, "A second picking should have been created for the MO")
        self.assertEqual(mo.components_availability_state, 'available', "MO should still be ready nevertheless")
        second_picking = mo.picking_ids.filtered(lambda p: p.state == 'assigned')
        self.assertRecordValues(second_picking.move_ids, [
            {'product_id': product_comp2.id, 'product_uom_qty': 1, 'picked': False},
        ])
        self.assertRecordValues(mo.move_raw_ids, [
            {'product_id': product_comp1.id, 'product_uom_qty': 1, 'quantity': 1, 'picked': False},
            {'product_id': product_comp2.id, 'product_uom_qty': 1, 'quantity': 1, 'picked': False},
        ])
        # Simulate adding more quantity from the Shop Floor.
        mo._update_order_line_info(product_comp2.id, 2, child_field='move_raw_ids', **kwargs)
        self.assertEqual(len(mo.picking_ids), 2, "No other picking should have been created")
        self.assertEqual(mo.components_availability_state, 'available', "MO should still be ready")
        self.assertRecordValues(second_picking.move_ids, [
            {'product_id': product_comp2.id, 'product_uom_qty': 2, 'picked': False},
        ])
        self.assertRecordValues(mo.move_raw_ids, [
            {'product_id': product_comp1.id, 'product_uom_qty': 1, 'quantity': 1, 'picked': False},
            {'product_id': product_comp2.id, 'product_uom_qty': 2, 'quantity': 2, 'picked': False},
        ])
        # starts the MO and simulate adding more quantity from the Shop Floor.
        mo.action_start()
        self.assertEqual(mo.state, 'progress')
        mo._update_order_line_info(product_comp2.id, 3, child_field='move_raw_ids', **kwargs)
        self.assertEqual(len(mo.picking_ids), 2, "No other picking should have been created")
        self.assertEqual(mo.components_availability_state, 'available', "MO should still be ready")
        self.assertRecordValues(second_picking.move_ids, [
            {'product_id': product_comp2.id, 'product_uom_qty': 3, 'picked': False},
        ])
        self.assertRecordValues(mo.move_raw_ids, [
            {'product_id': product_comp1.id, 'product_uom_qty': 1, 'quantity': 1, 'picked': False},
            {'product_id': product_comp2.id, 'product_uom_qty': 3, 'quantity': 3, 'picked': False},
        ])

    @users('test_without_hr_right')
    def test_shop_floor_my_wo_filter_with_pin_user(self):
        """Checks the shown Work Orders (in "My WO" section) are correctly
        refreshed when selected user uses a PIN code."""
        stock_location = self.warehouse.lot_stock_id
        # Create two employees (one with no PIN code and one with a PIN code.)
        self.env['hr.employee'].sudo().create([
            {'name': 'John Snow'},
            {'name': 'Queen Elsa', 'pin': '41213'},
        ])
        # Create some products and add enough quantity in stock for the components.
        final_product, comp_1, comp_2 = self.env['product.product'].create([{
            'name': name,
            'is_storable': True,
        } for name in ['Snowman', 'Snowball', 'Carrot']])
        self.env['stock.quant']._update_available_quantity(comp_1, stock_location, quantity=100)
        self.env['stock.quant']._update_available_quantity(comp_2, stock_location, quantity=100)
        # Configure all the needs to create a MO with at least one WO.
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Winter\'s Workshop',
            'time_start': 10,
            'time_stop': 5,
            'time_efficiency': 80,
        })
        bom = self.env['mrp.bom'].create({
            'product_id': final_product.id,
            'product_tmpl_id': final_product.product_tmpl_id.id,
            'product_uom_id': final_product.uom_id.id,
            'product_qty': 1.0,
            'consumption': 'flexible',
            'operation_ids': [
                Command.create({
                    'name': 'Build the Snowman',
                    'workcenter_id': workcenter.id,
                }),
            ],
            'bom_line_ids': [
                Command.create({'product_id': comp_1.id, 'product_qty': 3}),
                Command.create({'product_id': comp_2.id, 'product_qty': 1}),
            ],
        })
        # Mark the components as to consume in the operation so they appear in the Shop Floor.
        bom.bom_line_ids.operation_id = bom.operation_ids.id
        # Create, confirm and plan two MO.
        all_mo = self.env['mrp.production'].create([{
            'product_id': final_product.id,
            'product_qty': qty,
            'bom_id': bom.id,
        } for qty in [3, 5]])
        all_mo.action_confirm()
        all_mo.action_assign()
        all_mo.button_plan()
        self.start_tour('/odoo/shop-floor', 'test_shop_floor_my_wo_filter_with_pin_user', login='test_without_hr_right')

    @unittest.skip  # TODO: tour needs to be updated.
    def test_generate_serials_in_shopfloor(self):
        component1 = self.env['product.product'].create({
            'name': 'comp1',
            'is_storable': True,
        })
        component2 = self.env['product.product'].create({
            'name': 'comp2',
            'is_storable': True,
        })
        finished = self.env['product.product'].create({
            'name': 'finish',
            'is_storable': True,
        })
        byproduct = self.env['product.product'].create({
            'name': 'byprod',
            'is_storable': True,
            'tracking': 'serial',
        })
        stock_location = self.warehouse.lot_stock_id
        self.env['stock.quant']._update_available_quantity(component1, stock_location, quantity=100)
        self.env['stock.quant']._update_available_quantity(component2, stock_location, quantity=100)
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Assembly Line',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': finished.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                (0, 0, {'name': 'Assemble', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                (0, 0, {'product_id': component1.id, 'product_qty': 1}),
                (0, 0, {'product_id': component2.id, 'product_qty': 1}),
            ],
            'byproduct_ids': [
                (0, 0, {'product_id': byproduct.id, 'product_qty': 1}),
            ]
        })
        bom.byproduct_ids[0].operation_id = bom.operation_ids[0].id
        mo = self.env['mrp.production'].create({
            'product_id': finished.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.picking_type_id.prefill_shop_floor_lots = True
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()

        action = self.env["ir.actions.actions"]._for_xml_id("mrp_workorder.action_mrp_display")
        url = f"/odoo/action-{action['id']}"
        self.start_tour(url, "test_generate_serials_in_shopfloor", login='admin')
        self.assertEqual(mo.move_byproduct_ids.lot_ids.name, "00001")

    @users('test_without_hr_right')
    def test_partial_backorder_with_multiple_operations(self):
        """
        Create an MO for 10 units and 3 operations: op1, op2, op3. Process:
        - 10 units in op1
        - 7 units in op2
        - 5 units in op3
        Validate the MO for these 5 units and create a backorder. Check that each operation of the
        backorder displays the appropriate remaining quantity in the backend and in the shopfloor:
        - op1 shall be cancelled
        - op2 shall be processed for 3 units
        - op3 shall be processed for 5 units
        """
        finished = self.env['product.product'].create({
            'name': 'finish',
            'is_storable': True,
        })
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Assembly Line',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': finished.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'op1', 'workcenter_id': workcenter.id}),
                Command.create({'name': 'op2', 'workcenter_id': workcenter.id}),
                Command.create({'name': 'op3', 'workcenter_id': workcenter.id}),
            ],
        })

        # Cancel previous MOs and create a new one
        self.env['mrp.production'].search([('state', 'not in', ('cancel', 'done'))]).action_cancel()
        mo = self.env['mrp.production'].create({
            'name': 'MOBACK',
            'product_id': finished.id,
            'product_qty': 10,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()

        # wo_1 completely finished, wo_2 and wo_3 partially finished
        for wo, qty in zip(mo.workorder_ids, (10, 7, 5)):
            wo.button_start()
            with Form(mo) as fmo:
                fmo.qty_producing = qty
            wo.button_finish()

        # Create a backorder
        action = mo.button_mark_done()
        backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
        backorder.save().action_backorder()
        mo_backorder = mo.production_group_id.production_ids[-1]
        mo_backorder.button_plan()

        # Sanity check
        self.assertEqual(mo_backorder.workorder_ids[0].state, 'cancel')
        self.assertEqual(mo_backorder.workorder_ids[1].state, 'ready')

        self.start_tour("odoo/shop-floor", "test_partial_backorder_with_multiple_operations", login='test_without_hr_right')

    @users('test_without_hr_right')
    def test_change_qty_produced(self):
        """
            Check that component quantity matches the quantity produced set in the shop
            floor register production change to the quantity produced
            Example:
                move.uom_unit = 2.
                bom.final_quantity = 1
                MO.qty_producing = 5 -> should consume 10 components for move_raw.
                Confirm MO and update MO.qty_producing = 3
                Finish the workorder, then it should consume 6 components for move_raw.
            The above behaviour should be occur on the MO form and shop floor.
        """
        demo = self.env['product.product'].create({
            'name': 'DEMO'
        })
        comp1, comp2 = self.env['product.product'].create([{
            'name': name,
            'is_storable': True
        } for name in ['COMP1', 'COMP2']])
        work_center = self.env['mrp.workcenter'].create({"name": "WorkCenter", "time_start": 11})
        uom_unit = self.env.ref('uom.product_uom_unit')
        bom = self.env['mrp.bom'].create({
            'product_id': demo.id,
            'product_tmpl_id': demo.product_tmpl_id.id,
            'product_uom_id': uom_unit.id,
            'product_qty': 1.0,
            'type': 'normal',
            'operation_ids': [
                Command.create({'name': 'OP1', 'workcenter_id': work_center.id, 'time_cycle': 12, 'sequence': 1}),
                Command.create({'name': 'OP2', 'workcenter_id': work_center.id, 'time_cycle': 18, 'sequence': 2})
            ]
        })
        # Create a step to register production.
        self.env['quality.point'].create([{
                'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
                'product_ids': [Command.link(demo.id)],
                'operation_id': bom.operation_ids[1].id,
                'title': 'Register Production',
                'test_type_id': self.test_type_register_production.id,
        }])
        self.env['mrp.bom.line'].create([
            {
                'product_id': comp.id,
                'product_qty': qty,
                'bom_id': bom.id,
                'operation_id': operation.id,
            } for comp, qty, operation in zip([comp1, comp2], [1.0, 2.0], bom.operation_ids)
        ])
        self.env['stock.quant'].create([
            {
                'location_id': self.warehouse.lot_stock_id.id,
                'product_id': comp.id,
                'inventory_quantity': 20,
            } for comp in [comp1, comp2]
        ]).action_apply_inventory()

        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = bom
        mo_form.product_qty = 5
        mo = mo_form.save()
        mo.action_confirm()

        wo = mo.workorder_ids.sorted()[0]
        wo.button_start()
        wo.button_finish()
        self.start_tour("/odoo/shop-floor", "test_change_qty_produced", login='test_without_hr_right')
        self.assertEqual(mo.qty_producing, 3)
        for move in mo.move_raw_ids:
            if move.product_id.id == comp1.id:
                self.assertEqual(move.quantity, 5)
                self.assertTrue(move.picked)
            if move.product_id.id == comp2.id:
                self.assertEqual(move.quantity, 10)
                self.assertTrue(move.picked)

    @users('test_without_hr_right')
    def test_operator_assigned_to_all_work_orders(self):
        """
        Check that, if a custom operator is selected in the side panel, all work orders
        completed via Shop Floor are assigned to that operator.
        """
        employee = self.env['hr.employee'].sudo().create([{'name': 'Anita Olivier'}])
        product = self.env['product.product'].create({'name': 'P', 'is_storable': True})
        workcenter = self.env['mrp.workcenter'].create({'name': 'Workcenter1'})
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'OP1', 'workcenter_id': workcenter.id}),
                Command.create({'name': 'OP2', 'workcenter_id': workcenter.id}),
            ],
        })
        mo = self.env['mrp.production'].create({
            'product_id': product.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()

        self.start_tour('/odoo/shop-floor', 'test_operator_assigned_to_all_work_orders', login='test_without_hr_right')

        logs = mo.workorder_ids.time_ids
        self.assertEqual(len(logs), 2, 'Both operations should be logged.')
        self.assertEqual(logs[0].employee_id, employee, 'OP1 should be assigned to "Anita Olivier"')
        self.assertEqual(
            logs[0].description, 'Time Tracking: Anita Olivier',
            'The description of OP1 should mention "Anita Olivier"'
        )
        self.assertEqual(logs[1].employee_id, employee, 'OP2 should be assigned to "Anita Olivier"')
        self.assertEqual(
            logs[1].description, 'Time Tracking: Anita Olivier',
            'The description of OP2 should mention "Anita Olivier"'
        )

    @users('test_without_hr_right')
    def test_automatic_backorder_no_redirect(self):
        """
        Test that the backorder is created without redirecting to the
        production form on shopfloor. This is the case when the backorder
        is created automatically by the system on shopfloor.
        Also check that the production can be closed if there is nothing to backorder.
        """
        self.warehouse.manu_type_id.create_backorder = 'always'
        final_product, component = self.env['product.product'].create([
            {
                'name': 'Product',
                'type': 'consu',
                'is_storable': True,
            },
            {
                'name': 'Component1',
                'type': 'consu',
                'is_storable': True,
                'tracking': 'none',
            },
        ])
        self.env['stock.quant']._update_available_quantity(product_id=component, location_id=self.warehouse.lot_stock_id, quantity=100)
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Workcenter1',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': final_product.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'Operation1', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                Command.create({'product_id': component.id, 'product_qty': 1}),
            ]
        })
        # Create a step to register production.
        self.env['quality.point'].create([{
                'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
                'product_ids': [Command.link(final_product.id)],
                'operation_id': bom.operation_ids[0].id,
                'title': 'Register Production',
                'test_type_id': self.test_type_register_production.id,
        }])
        mo = self.env['mrp.production'].create({
                'name': "MOBACK",
                'product_id': final_product.id,
                'product_qty': 2,
                'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()
        self.start_tour("/odoo/shop-floor", "test_automatic_backorder_no_redirect", login='test_without_hr_right')
        self.assertRecordValues(mo.production_group_id.production_ids.sorted('name'), [
            {'name': 'MOBACK-001', 'state': 'done'},
            {'name': 'MOBACK-002', 'state': 'done'},
        ])

    @users('test_without_hr_right')
    def test_shop_floor_access(self):
        mrp_partner = self.env['res.partner'].create({'name': 'mrp_user'})
        self.env['res.users'].sudo().create({
            'login': 'mrp_user',
            'partner_id': mrp_partner.id,
            'group_ids': [Command.set(self.env.ref('mrp.group_mrp_routings').ids)],
        })
        self.env['mrp.workcenter'].create({'name': 'Workcenter1'})
        self.start_tour('/odoo', 'test_shop_floor_access', login='test_without_hr_right')

    def test_set_qty_producing(self):
        user_admin = self.env.ref('base.user_admin')
        user_admin.email = "admin@example.com"
        component, final_product = self.env['product.product'].create([{
            'name': 'component',
            'is_storable': True,
        }, {
            'name': 'final product',
            'is_storable': True,
            'tracking': 'serial',
        }])
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Assembly Line',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': final_product.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'Operation1', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                Command.create({'product_id': component.id, 'product_qty': 1}),
            ]
        })
        self.env['quality.point'].create([{
                'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
                'product_ids': [Command.link(final_product.id)],
                'title': 'Register Production',
                'test_type_id': self.test_type_register_production.id,
        }])
        mo = self.env['mrp.production'].create({
            'product_id': final_product.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })

        mo.action_confirm()
        wo = mo.workorder_ids[0]
        Form.from_action(self.env, wo.action_add_step())\
            .save() \
            .with_user(user_admin) \
            .add_check_in_chain()
        wo.set_qty_producing()

        first_check = wo.check_ids[0]
        last_check = wo.check_ids[1]
        new_check = last_check.copy()
        wo.set_qty_producing()

        self.assertEqual(last_check.next_check_id, new_check)
        self.assertEqual(new_check.previous_check_id, last_check)
        self.assertEqual(new_check.next_check_id, first_check)
        self.assertEqual(first_check.previous_check_id, new_check)
        self.assertFalse(first_check.next_check_id)
        self.assertEqual(wo.current_quality_check_id, first_check)
        self.assertFalse(wo.allow_producing_quantity_change)

    def test_shop_floor_unsynced_bom(self):
        """ Check that when a component that has been removed from a BoM with
            a not done MO, it still shows the component in the shop floor for
            that MO.
        """
        demo = self.env['product.product'].create({'name': 'DEMO'})
        comp1, comp2 = self.env['product.product'].create([{
            'name': name,
            'is_storable': True
        } for name in ['COMP1', 'COMP2']])
        work_center = self.env['mrp.workcenter'].create({"name": "WorkCenter", "time_start": 11})
        bom = self.env['mrp.bom'].create({
            'product_id': demo.id,
            'product_tmpl_id': demo.product_tmpl_id.id,
            'product_uom_id': self.env.ref('uom.product_uom_unit').id,
            'product_qty': 1.0,
            'type': 'normal',
            'operation_ids': [
                Command.create({'name': 'OP1', 'workcenter_id': work_center.id, 'time_cycle': 12, 'sequence': 1}),
                Command.create({'name': 'OP2', 'workcenter_id': work_center.id, 'time_cycle': 18, 'sequence': 2})
            ]
        })
        # Create a step to register production.
        self.env['quality.point'].create([{
            'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
            'product_ids': [Command.link(demo.id)],
            'operation_id': bom.operation_ids[1].id,
            'title': 'Register Production',
            'test_type_id': self.test_type_register_production.id,
        }])
        self.env['mrp.bom.line'].create([
            {
                'product_id': comp.id,
                'product_qty': qty,
                'bom_id': bom.id,
                'operation_id': operation.id,
            } for comp, qty, operation in zip([comp1, comp2], [1.0, 2.0], bom.operation_ids)
        ])
        self.env['stock.quant'].create([
            {
                'location_id': self.warehouse.lot_stock_id.id,
                'product_id': comp.id,
                'inventory_quantity': 20,
            } for comp in [comp1, comp2]
        ]).action_apply_inventory()

        mo = self.env['mrp.production'].create({
            'product_id': demo.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()
        # Remove one component from the BoM, so that the MO and BoM are unsynced
        bom.bom_line_ids[0].unlink()

        self.start_tour("/odoo/shop-floor", "test_shop_floor_unsynced_bom", login='admin')

        self.assertEqual(mo.qty_producing, 1)
        for move in mo.move_raw_ids:
            if move.product_id.id == comp1.id:
                self.assertEqual(move.quantity, 1)
                self.assertTrue(move.picked)
            if move.product_id.id == comp2.id:
                self.assertEqual(move.quantity, 2)
                self.assertTrue(move.picked)

    def test_product_consumption(self):
        """ Test that we generate the correct move when completing from the shopfloor
        a MO with component consumption. The component is tracked by lot, and use kg
        as its default UoM.
        BoM: component 50g => product 1 Unit
        """
        # user need to be in the production lot group to be able to see the lot id in the quant selection view.
        self.env.user.write({'group_ids': [Command.link(self.ref('stock.group_production_lot'))]})

        workcenter = self.env['mrp.workcenter'].create({'name': 'Workcenter1'})
        component, product = self.env["product.product"].create([
                {
                    "name": "component",
                    "is_storable": True,
                    "tracking": "lot",
                    "uom_id": self.ref("uom.product_uom_kgm"),
                },
                {
                    "name": "product",
                    "is_storable": True,
                },
        ])
        bom = self.env['mrp.bom'].create({
            'product_id': product.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1,
            'operation_ids': [
                Command.create({'name': 'consumption', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                Command.create({
                    'product_id': component.id,
                    'product_qty': 50,
                    'product_uom_id': self.ref('uom.product_uom_gram'),
                }),
            ],
        })
        lot_1, lot_2 = self.env['stock.lot'].create([
            {'name': 'Lot 1', 'product_id': component.id},
            {'name': 'Lot 2', 'product_id': component.id},
        ])
        bom.bom_line_ids.operation_id = bom.operation_ids.id
        self.env['stock.quant']._update_available_quantity(component, self.warehouse.lot_stock_id, quantity=100, lot_id=lot_1)
        self.env['stock.quant']._update_available_quantity(component, self.warehouse.lot_stock_id, quantity=100, lot_id=lot_2)
        mo = self.env['mrp.production'].create({
            'product_id': product.id,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        self.start_tour('/odoo/shop-floor', 'test_product_consumption', login='admin')

        self.assertRecordValues(mo.move_raw_ids, [
            {
                'product_id': component.id,
                'product_qty': 0.05,
                'product_uom_qty': 50.0,
                'lot_ids': lot_1.ids,
                'product_uom': self.ref('uom.product_uom_gram'),
            },
        ])
