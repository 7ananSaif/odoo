# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo import Command


class TestQuality(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        grp_workorder = cls.env.ref('mrp.group_mrp_routings')
        cls.env.user.write({'group_ids': [(4, grp_workorder.id)]})

        cls.product_1 = cls.env['product.product'].create({'name': 'Table'})
        cls.product_2 = cls.env['product.product'].create({'name': 'Table top'})
        cls.product_3 = cls.env['product.product'].create({'name': 'Table leg'})
        cls.workcenter_1 = cls.env['mrp.workcenter'].create({
            'name': 'Test Workcenter',
            'time_start': 10,
            'time_stop': 5,
            'time_efficiency': 80,
        })
        cls.bom = cls.env['mrp.bom'].create({
            'product_id': cls.product_1.id,
            'product_tmpl_id': cls.product_1.product_tmpl_id.id,
            'product_uom_id': cls.product_1.uom_id.id,
            'product_qty': 1.0,
            'consumption': 'flexible',
            'operation_ids': [
                (0, 0, {'name': 'Assembly', 'workcenter_id': cls.workcenter_1.id, 'time_cycle': 15, 'sequence': 1}),
            ],
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {'product_id': cls.product_2.id, 'product_qty': 1}),
                (0, 0, {'product_id': cls.product_3.id, 'product_qty': 4})
            ]
        })

    def test_quality_point_onchange(self):
        quality_point_form = Form(self.env['quality.point'].with_context(default_product_ids=[self.product_2.id]))
        # Form should keep the default products set
        self.assertEqual(len(quality_point_form.product_ids), 1)
        self.assertEqual(quality_point_form.product_ids[0].id, self.product_2.id)
        # <field name="operation_id" invisible="not is_workorder_step"/>
        # @api.depends('operation_id', 'picking_type_ids')
        # def _compute_is_workorder_step(self):
        #     for quality_point in self:
        #         quality_point.is_workorder_step = quality_point.operation_id or quality_point.picking_type_ids and\
        #             all(pt.code == 'mrp_operation' for pt in quality_point.picking_type_ids)
        quality_point_form.picking_type_ids.add(
            self.env['stock.picking.type'].search([('code', '=', 'mrp_operation')], limit=1)
        )
        # Select a workorder operation
        quality_point_form.operation_id = self.bom.operation_ids[0]
        # Product should be replaced by the product linked to the bom
        self.assertEqual(len(quality_point_form.product_ids), 1)
        self.assertEqual(quality_point_form.product_ids[0].id, self.bom.product_id.id)

    def test_delete_move_linked_to_quality_check(self):
        """
        Test that a quality check is deleted when its linked move is deleted.
        """
        self.bom.bom_line_ids.product_id.tracking = 'lot'
        self.bom.bom_line_ids.product_id.is_storable = True
        self.bom.operation_ids[0].quality_point_ids = [Command.create({
            'product_ids': [(4, self.product_1.id)],
            'picking_type_ids': [(4, self.env['stock.picking.type'].search([('code', '=', 'mrp_operation')], limit=1).id)],
            'test_type_id': self.env.ref('mrp_workorder.test_type_register_consumed_materials').id,
            'component_id': self.product_2.id,
        })]
        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = self.bom
        mo = mo_form.save()
        mo.action_confirm()
        qc = self.env['quality.check'].search([('product_id', '=', self.bom.product_id.id)])[-1]
        move = qc.move_id
        self.assertEqual(len(qc), 1)
        self.assertFalse(move.move_line_ids)
        move.state = 'draft'
        move.unlink()
        self.assertFalse(move.exists())
        self.assertFalse(qc.exists())

    def test_label_printed_qty(self):
        """
        Check that the label printing instructions print the expected quantities.
        """
        super_product = self.env['product.product'].create({
            'name': 'Super Product',
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
        })
        bom = self.env['mrp.bom'].create({
            'product_id': super_product.id,
            'product_tmpl_id': super_product.product_tmpl_id.id,
            'product_uom_id': super_product.uom_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'print label', 'workcenter_id': self.workcenter_1.id})
            ],
            'type': 'normal',
        })

        self.env['quality.point'].create({
            'title': 'Print Label',
            'product_ids': [Command.link(super_product.id)],
            'operation_id': bom.operation_ids.id,
            'test_type_id': self.ref('mrp_workorder.test_type_print_label')
        })
        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = bom
        mo_form.product_qty = 10
        mo = mo_form.save()
        mo.action_confirm()

        self.assertEqual(mo.workorder_ids.current_quality_check_id._get_print_qty(), 10)
        with Form(mo) as mo_form:
            mo_form.qty_producing = 7.0
        self.assertEqual(mo.workorder_ids.current_quality_check_id._get_print_qty(), 7)

    def test_copy_quality_check(self):
        """Test that a copied quality check is correctly added into the chain.

            Scenario:
                - Given a chain of quality checks A -> B -> C.
                - When B is copied.
                - Then the resulting chain should be A -> B -> B' -> C,
                ensuring the copied quality check is inserted directly after its original quality check.
        """
        quality_point = self.env['quality.point'].create({
            'product_ids': [(4, self.product_1.id)],
        })
        quality_alert_team = self.env['quality.alert.team'].create({
            'name': 'Quality Team',
        })
        check_vals = {
            'product_id': self.product_1.id,
            'point_id': quality_point.id,
            'team_id': quality_alert_team.id,
        }
        quality_checks = self.env['quality.check'].create([check_vals, check_vals, check_vals])

        # Create a chain of Quality checks 0 -> 1 -> 2
        quality_checks[1]._insert_in_chain('after', quality_checks[0])
        quality_checks[2]._insert_in_chain('after', quality_checks[1])

        new_check = quality_checks[1].copy()

        # chain of Quality checks should be 0 -> 1 -> Copy of 1 -> 2
        self.assertEqual(quality_checks[1].next_check_id, new_check)
        self.assertEqual(new_check.previous_check_id, quality_checks[1])
        self.assertEqual(new_check.next_check_id, quality_checks[2])
