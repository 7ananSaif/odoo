# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.fields import Command

from .test_common import TestQualityMrpCommon


class TestQualityCheck(TestQualityMrpCommon):

    def test_00_production_quality_check(self):

        """Test quality check on production order and its backorder."""

        # Create Quality Point for product Laptop Customized with Manufacturing Operation Type.
        self.qality_point_test1 = self.env['quality.point'].create({
            'product_ids': [(4, self.product_id)],
            'picking_type_ids': [(4, self.picking_type_id)],
        })

        # Check that quality point created.
        assert self.qality_point_test1, "First Quality Point not created for Laptop Customized."

        # Create Production Order of Laptop Customized to produce 5.0 Unit.
        production_form = Form(self.env['mrp.production'])
        production_form.product_id = self.env['product.product'].browse(self.product_id)
        production_form.product_qty = 5.0
        self.mrp_production_qc_test1 = production_form.save()

        # Check that Production Order of Laptop Customized to produce 5.0 Unit is created.
        assert self.mrp_production_qc_test1, "Production Order not created."

        # Perform check availability and produce product.
        self.mrp_production_qc_test1.action_confirm()
        self.mrp_production_qc_test1.action_assign()

        mo_form = Form(self.mrp_production_qc_test1)
        mo_form.qty_producing = self.mrp_production_qc_test1.product_qty - 1
        mo_form.lot_producing_ids.set(self.lot_product_27_0)
        for move in self.mrp_production_qc_test1.move_raw_ids:
            details_operation_form = Form(move, view=self.env.ref('stock.view_stock_move_operations'))
            with details_operation_form.move_line_ids.edit(0) as ml:
                ml.lot_id = self.lot_product_product_drawer_drawer_0 if ml.product_id == self.product_product_drawer_drawer else self.lot_product_product_drawer_case_0
            details_operation_form.save()

        self.mrp_production_qc_test1 = mo_form.save()
        self.mrp_production_qc_test1.move_raw_ids[0].picked = True
        # Check Quality Check for Production is created and check it's state is 'none'.
        self.assertEqual(len(self.mrp_production_qc_test1.check_ids), 1)
        self.assertEqual(self.mrp_production_qc_test1.check_ids.quality_state, 'none')

        # 'Pass' Quality Checks of production order.
        self.mrp_production_qc_test1.check_ids.do_pass()

        # Set MO Done and create backorder
        action = self.mrp_production_qc_test1.button_mark_done()
        consumption_warning = Form(self.env['mrp.consumption.warning'].with_context(**action['context']))
        action = consumption_warning.save().action_confirm()
        backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
        backorder.save().action_backorder()

        # Now check state of quality check.
        self.assertEqual(self.mrp_production_qc_test1.check_ids.quality_state, 'pass')
        # Check that the Quality Check was created on the backorder
        self.assertEqual(len(self.mrp_production_qc_test1.production_group_id.production_ids[-1].check_ids), 1)

    def test_02_quality_check_scrapped(self):
        """
        Test that when scrapping a manufacturing order, no quality check is created for that move
        """
        product = self.env['product.product'].create({'name': 'Time'})
        component = self.env['product.product'].create({'name': 'Money'})

        # Create a quality point for Manufacturing on All Operations (All Operations is set by default)
        qp = self.env['quality.point'].create({'picking_type_ids': [(4, self.picking_type_id)]})
        # Create a Manufacturing order for a product
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = product
        mri_form = mo_form.move_raw_ids.new()
        mri_form.product_id = component
        mri_form.product_uom_qty = 1
        mri_form.save()
        mo = mo_form.save()
        mo.action_confirm()
        # Delete the created quality check
        qc = self.env['quality.check'].search([('product_id', '=', product.id), ('point_id', '=', qp.id)])
        qc.unlink()

        # Scrap the Manufacturing Order
        scrap = self.env['stock.scrap'].with_context(active_model='mrp.production', active_id=mo.id).create({
            'product_id': product.id,
            'scrap_qty': 1.0,
            'product_uom_id': product.uom_id.id,
            'production_id': mo.id
        })
        scrap.do_scrap()
        self.assertEqual(len(self.env['quality.check'].search([('product_id', '=', product.id), ('point_id', '=', qp.id)])), 0, "Quality checks should not be created for scrap moves")

    def test_03_quality_check_on_operations(self):
        """ Test Quality Check creation of 'operation' type, meaning only one QC will be created per MO.
        """
        quality_point_operation_type = self.env['quality.point'].create({
            'picking_type_ids': [(4, self.picking_type_id)],
            'measure_on': 'operation',
            'test_type_id': self.env.ref('quality_control.test_type_passfail').id
        })

        production_form = Form(self.env['mrp.production'])
        production_form.product_id = self.env['product.product'].browse(self.product_id)
        production_form.product_qty = 5.0
        production = production_form.save()
        production.action_confirm()

        self.assertEqual(len(production.check_ids), 1)
        self.assertEqual(production.check_ids.point_id, quality_point_operation_type)
        self.assertEqual(production.check_ids.production_id, production)

        # Do the quality checks and create backorder
        production.check_ids.do_pass()
        production.qty_producing = 3.0
        production.lot_producing_ids = self.lot_product_27_0
        for move in production.move_raw_ids:
            details_operation_form = Form(move, view=self.env.ref('stock.view_stock_move_operations'))
            with details_operation_form.move_line_ids.edit(0) as ml:
                ml.lot_id = self.lot_product_product_drawer_drawer_0 if ml.product_id == self.product_product_drawer_drawer else self.lot_product_product_drawer_case_0
            details_operation_form.save()
        production.move_raw_ids[1].picked = True
        action = production.button_mark_done()
        consumption_warning = Form(self.env['mrp.consumption.warning'].with_context(**action['context']))
        action = consumption_warning.save().action_confirm()
        backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
        backorder.save().action_backorder()
        production_backorder = production.production_group_id.production_ids[-1]
        self.assertEqual(len(production_backorder.check_ids), 1)
        self.assertEqual(production_backorder.check_ids.point_id, quality_point_operation_type)
        self.assertEqual(production_backorder.check_ids.production_id, production_backorder)

    def test_quality_check_serial_backorder(self):
        """Create a MO for a product tracked by serial number.
        Generate all but one serial numbers and create a back order.
        """
        # Set up Products
        product_to_build = self.env['product.product'].create({
            'name': 'Young Tom',
            'is_storable': True,
            'tracking': 'serial',
        })
        product_to_use_1 = self.env['product.product'].create({
            'name': 'Botox',
            'is_storable': True,
        })
        product_to_use_2 = self.env['product.product'].create({
            'name': 'Old Tom',
            'is_storable': True,
        })
        bom_1 = self.env['mrp.bom'].create({
            'product_id': product_to_build.id,
            'product_tmpl_id': product_to_build.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {'product_id': product_to_use_2.id, 'product_qty': 1}),
                (0, 0, {'product_id': product_to_use_1.id, 'product_qty': 1})
            ]})

        # Create Quality Point for product Laptop Customized with Manufacturing Operation Type.
        self.qality_point_test1 = self.env['quality.point'].create({
            'product_ids': [(4, product_to_build.id)],
            'picking_type_ids': [(4, self.picking_type_id)],
        })

        # Start manufacturing
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = product_to_build
        mo_form.bom_id = bom_1
        mo_form.product_qty = 5
        mo = mo_form.save()
        mo.action_confirm()

        # Make some stock and reserve
        for product in mo.move_raw_ids.product_id:
            self.env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': product.id,
                'inventory_quantity': 100,
                'location_id': mo.location_src_id.id,
            })._apply_inventory()
        mo.action_assign()
        # 'Pass' Quality Checks of production order.
        self.assertEqual(len(mo.check_ids), 1)
        mo.check_ids.do_pass()

        action = mo.action_generate_serial()
        wizard = Form.from_action(self.env, action)
        wizard.lot_name = 'sn#1'
        wizard.lot_quantity = mo.product_qty - 1
        action = wizard.save().action_generate_serial_numbers()
        wizard = Form.from_action(self.env, action)
        wizard.save().action_apply()

        # Last MO in sequence is the backorder
        bo = mo.production_group_id.production_ids[-1]
        self.assertEqual(len(bo.check_ids), 1)

    def test_failure_quality_point_location_on_operation(self):
        """ test the failure location is hidden in case of manufacturing quality point """
        self.env['quality.point'].create({
            'measure_on': 'operation',
            'picking_type_ids': [Command.link(self.picking_type_id)],
            'test_type_id': self.env.ref('quality_control.test_type_passfail').id,
            'failure_location_ids': [Command.link(self.failure_location.id)],
        })
        production_form = Form(self.env['mrp.production'])
        production_form.product_id = self.env['product.product'].browse(self.product_id)
        production_form.product_qty = 1
        production = production_form.save()
        production.action_confirm()
        production.qty_producing = 1
        production.lot_producing_ids = self.lot_product_27_0
        production.move_raw_ids[0].move_line_ids[0].lot_id = self.lot_product_product_drawer_drawer_0
        production.move_raw_ids[1].move_line_ids[0].lot_id = self.lot_product_product_drawer_case_0
        production.move_raw_ids.picked = True
        check_action = production.check_quality()
        quality_wizard = Form(self.env[check_action['res_model']].with_context(**check_action['context']))
        quality_wizard = quality_wizard.save()
        action = quality_wizard.do_fail()
        quality_wizard = Form(self.env[action['res_model']].with_context(**action['context']))
        quality_wizard = quality_wizard.save()
        self.assertEqual(quality_wizard.failure_location_id, self.failure_location)
        quality_wizard.confirm_fail()
        self.assertEqual(production.location_dest_id.id, self.location_dest_id)
        self.assertEqual(production.move_finished_ids.location_dest_id, self.failure_location)
        production.button_mark_done()
        self.assertEqual(production.state, 'done')
        self.assertEqual(production.move_finished_ids.location_dest_id, self.failure_location)

    def test_failure_quality_point_location(self):
        """ test the failure location is hidden in case of manufacturing quality point """
        quality_point = self.env['quality.point'].create({
            'measure_on': 'product',
            'picking_type_ids': [Command.link(self.picking_type_id)],
            'test_type_id': self.env.ref('quality_control.test_type_passfail').id,
        })
        self.assertTrue(quality_point.show_failure_location)
        quality_point.test_type_id = self.env.ref('quality.test_type_instructions')
        self.assertFalse(quality_point.show_failure_location)
        quality_point.test_type_id = self.env.ref('quality_control.test_type_passfail')
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Test workcenter',
        })

        operation = self.env['mrp.routing.workcenter'].create({
            'name': 'Test order',
            'workcenter_id': workcenter.id,
            'bom_id': self.bom.id,
            'time_cycle_manual': 30,
        })
        quality_point.operation_id = operation
        self.assertFalse(quality_point.show_failure_location)

    def test_production_product_control_point(self):
        """Test quality control point on production order."""

        # Create Quality Point for product with Manufacturing Operation Type.
        self.qality_point_test1 = self.env['quality.point'].create({
            'picking_type_ids': [(4, self.picking_type_id)],
            'measure_on': 'product',
        })

        self.bom.consumption = 'flexible'
        # Create Production Order of 5.0 Unit.
        production_form = Form(self.env['mrp.production'])
        production_form.product_id = self.env['product.product'].browse(self.product_id)
        production_form.product_qty = 5.0
        self.mrp_production_qc_test1 = production_form.save()

        # Perform check availability and produce product.
        self.mrp_production_qc_test1.action_confirm()
        self.mrp_production_qc_test1.action_assign()

        mo_form = Form(self.mrp_production_qc_test1)
        mo_form.qty_producing = self.mrp_production_qc_test1.product_qty
        mo_form.lot_producing_ids.set(self.lot_product_27_0)
        for move in self.mrp_production_qc_test1.move_raw_ids:
            details_operation_form = Form(move, view=self.env.ref('stock.view_stock_move_operations'))
            with details_operation_form.move_line_ids.edit(0) as ml:
                ml.lot_id = self.lot_product_product_drawer_drawer_0 if ml.product_id == self.product_product_drawer_drawer else self.lot_product_product_drawer_case_0
            details_operation_form.save()

        self.mrp_production_qc_test1 = mo_form.save()
        self.mrp_production_qc_test1.move_raw_ids[0].picked = True
        # Check Quality Check for Production is created.
        self.assertEqual(len(self.mrp_production_qc_test1.check_ids), 1)

        # 'Pass' Quality Checks of production order.
        self.mrp_production_qc_test1.check_ids.do_pass()

        # Set MO Done.
        self.mrp_production_qc_test1.button_mark_done()

        # Now check that no new quality check are created.
        self.assertEqual(len(self.mrp_production_qc_test1.check_ids), 1)

    def test_quantity_control_point_with_production(self):
        """Test that it's not possible to create a Quantity quality check type with a manufacturing operation type."""
        with self.assertRaises(UserError):
            self.qality_point_test1 = self.env['quality.point'].create({
                'picking_type_ids': [Command.link(self.picking_type_id)],
                'measure_on': 'move_line',
            })

    def test_manufacture_picking_type_with_product_categ_in_qp(self):
        """Create a quality point of type measure on'operation' with the manufacturing
        picking type and product category set, and verify that the quality check
        is correctly created.
        """
        self.bom.product_tmpl_id.categ_id = self.product_category_base
        qp = self.env['quality.point'].create({
            'product_category_ids': [Command.link(self.product_category_base.id)],
            'picking_type_ids': [Command.link(self.picking_type_id)],
            'measure_on': 'operation',
            'test_type_id': self.env.ref('quality_control.test_type_passfail').id,
        })
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 20,
            'move_raw_ids': [
                Command.create({
                    'product_id': self.product_3.id,
                    'product_uom_qty': 10,
                })
            ],
        })
        production.action_confirm()
        self.assertEqual(production.state, 'confirmed')
        self.assertEqual(len(production.check_ids), 1)
        self.assertEqual(production.check_ids.point_id, qp)
        production.check_ids.do_pass()
        self.assertEqual(production.check_ids.quality_state, 'pass')
