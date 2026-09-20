# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo.addons.mrp_account.tests.test_mrp_account import TestMrpAccount
from odoo.tests import Form
from freezegun import freeze_time


class TestReportsCommon(TestMrpAccount):

    @freeze_time('2022-05-28')
    def test_mrp_avg_cost_calculation(self):
        """
            Check that the average cost is calculated based on the quantity produced in each MO

            - Final product Bom structure:
                - product_4: qty: 2, cost: $20
                - product_3: qty: 3, cost: $50

            - Work center > costs_hour = $80

            1:/ MO1:
                - qty to produce: 10 units
                - work_order duration: 300
                unit_component_cost = ((20 * 2) + (50 * 3)) = 190
                unit_duration = 300 / 10 = 30
                unit_operation_cost = (80 / 60) * 30'unit_duration' = 40
                unit_cost = 190 + 40 = 250

            2:/ MO2:
                - update product_3 cost to: $30
                - qty to produce: 20 units
                - work order duration: 600
                unit_component_cost = ((20 * 2) + (30 * 3)) = $130
                unit_duration = 600 / 20 = 30
                unit_operation_cost = (80 / 60) * 30'unit_duration' = 40
                unit_cost = 130 + 40 = 170

            total_qty_produced = 30
            avg_unit_component_cost = ((190 * 10) + (130 * 20)) / 30 = $150
            avg_unit_operation_cost = ((40*20) + (40*10)) / 30 = $40
            avg_unit_duration = (600 + 300) / 30 = 30
            avg_unit_cost = avg_unit_component_cost + avg_unit_operation_cost = $190
        """
        bom = self.bom_2.copy()
        bom.type = 'normal'
        bom.product_id = self.product_6

        # Make some stock and reserve
        for product in bom.bom_line_ids.product_id:
            self.env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': product.id,
                'inventory_quantity': 1000,
                'location_id': self.stock_location_components.id,
            })._apply_inventory()

        # Change product_4 UOM to unit
        bom.bom_line_ids[0].product_uom_id = self.ref('uom.product_uom_unit')

        # Update the work center cost
        bom.operation_ids.workcenter_id.costs_hour = 80

        # MO_1
        self.product_4.standard_price = 20
        self.product_3.standard_price = 50
        production_form = Form(self.env['mrp.production'])
        production_form.bom_id = bom
        production_form.product_qty = 10
        mo_1 = production_form.save()
        mo_1.action_confirm()

        mo_1.button_plan()
        wo = mo_1.workorder_ids
        wo.button_start()
        wo.duration = 300
        wo.qty_producing = 10

        mo_1.button_mark_done()

        # MO_2
        self.product_3.standard_price = 30
        production_form = Form(self.env['mrp.production'])
        production_form.bom_id = bom
        production_form.product_qty = 20
        mo_2 = production_form.save()
        mo_2.action_confirm()

        mo_2.button_plan()
        wo = mo_2.workorder_ids
        wo.button_start()
        wo.duration = 600
        wo.qty_producing = 20

        mo_2.button_mark_done()

        # must flush else SQL request in report is not accurate
        self.env.flush_all()

        report = self.env['mrp.report']._read_group(
            [('product_id', '=', bom.product_id.id)],
            aggregates=['unit_cost:avg', 'unit_component_cost:avg', 'unit_operation_cost:avg', 'unit_duration:avg'],
        )[0]
        unit_cost, unit_component_cost, unit_operation_cost, unit_duration = report
        self.assertEqual(unit_cost, 190)
        self.assertEqual(unit_component_cost, 150)
        self.assertEqual(unit_operation_cost, 40)
        self.assertEqual(unit_duration, 30)
