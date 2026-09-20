#  -*- coding: utf-8 -*-
#  Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime
from freezegun import freeze_time

from odoo import Command
from odoo.tests import Form, common, users
from odoo.exceptions import UserError

class TestWorkorderDurationHr(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        grp_workorder = cls.env.ref('mrp.group_mrp_routings')
        cls.env.user.write({'group_ids': [(4, grp_workorder.id)]})
        cls.workcenter = cls.env['mrp.workcenter'].create({
            'name': 'Nuclear Workcenter',
            'employee_ids': [
                Command.create({
                    'name': 'Qian Xuesen',
                    'pin': '1234'}),
                Command.create({
                    'name': 'Yu Min',
                    'pin': '5678'})]})
        cls.employee_1 = cls.workcenter.employee_ids[0]
        cls.employee_2 = cls.workcenter.employee_ids[1]
        cls.final_product = cls.env['product.product'].create({
            'name': 'DF-41',
            'is_storable': True,
            'tracking': 'none'})
        cls.component = cls.env['product.product'].create({
            'name': 'RBCC engine',
            'is_storable': True,
            'tracking': 'none'})
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.final_product.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({
                    'name': 'fuel injection',
                    'workcenter_id': cls.workcenter.id,
                    'time_cycle': 12,
                    'sequence': 1})]})
        cls.env['mrp.bom.line'].create({
            'product_id': cls.component.id,
            'product_qty': 1.0,
            'bom_id': cls.bom.id})
        mo_form = Form(cls.env['mrp.production'])
        mo_form.product_id = cls.final_product
        mo_form.bom_id = cls.bom
        mo_form.product_qty = 1
        cls.mo = mo_form.save()

        cls.user_without_hr_right = cls.env['res.users'].create({
            'name': 'Test without hr right',
            'login': 'test_without_hr_right',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('mrp.group_mrp_manager').id,
                cls.env.ref('mrp.group_mrp_routings').id
            ])],
        })

    def test_workorder_duration(self):
        """Test the duration of workorder is computed based on employee time interval
        """
        self.mo.action_confirm()
        wo = self.mo.workorder_ids[0]
        with freeze_time('2027-10-01 10:00:00'):
            wo.start_employee(self.employee_1.id)
            self.env.flush_all()   # need flush to trigger compute
        with freeze_time('2027-10-01 11:00:00'):
            wo.stop_employee([self.employee_1.id])
            self.env.flush_all()   # need flush to trigger compute
        self.assertEqual(wo.duration, 60)

        # add new time interval that overlapped with the previous one
        wo_form = Form(wo)
        with wo_form.time_ids.new() as line:
            line.employee_id = self.employee_2
            line.date_start = datetime(2027, 10, 1, 10, 30, 0)
            line.date_end = datetime(2027, 10, 1, 11, 30, 0)
            line.loss_id = self.env.ref('mrp.block_reason7')
        wo_form.save()
        self.assertEqual(wo.duration, 90)

        # add new time interval that not overlapped with the previous ones
        with wo_form.time_ids.new() as line:
            line.employee_id = self.employee_1
            line.date_start = datetime(2027, 10, 1, 12, 30, 0)
            line.date_end = datetime(2027, 10, 1, 13, 30, 0)
            line.loss_id = self.env.ref('mrp.block_reason7')
        wo_form.save()
        self.assertEqual(wo.duration, 150)
        # Check that the work order cannot be started when it's finished
        self.mo.qty_producing = 1
        self.env.user.employee_id = self.employee_1
        wo.do_finish()
        self.assertEqual(wo.state, 'done')
        with self.assertRaises(UserError):
            wo.button_start()

    def test_allowed_employees_restriction(self):
        """
        Ensure that the employee linked to the current user cannot start a work order
        in a work center where this employee is not authorized to work.
        """
        self.workcenter.employee_ids = self.employee_1
        self.assertEqual(self.mo.workorder_ids.workcenter_id, self.workcenter)
        self.env.user.employee_id = self.employee_2
        with self.assertRaises(UserError):
            self.mo.workorder_ids.button_start()
        self.env.user.employee_id = self.employee_1
        self.mo.workorder_ids.button_start()
        self.assertEqual(self.mo.workorder_ids.state, 'progress')

    def test_assigned_employee_workorder_productivity(self):
        """Ensure that the employee assigned to the work order is the one
        linked to productivity when validating the MO.
        """
        self.env.user.employee_ids = [Command.link(self.employee_2.id)]
        self.mo.workorder_ids.employee_assigned_ids = self.employee_1
        self.mo.button_mark_done()
        self.assertTrue(self.mo.workorder_ids)
        self.assertEqual(self.mo.state, 'done')
        self.assertEqual(self.mo.workorder_ids.time_ids.employee_id, self.employee_1)

    def test_estimated_employee_cost_valuation(self):
        """ Test that operations with 'estimated' cost correctly compute the employee cost.
        The cost should be equal to workcenter.employee_costs_hour * workorder.duration_expected. """
        self.bom.operation_ids.cost_mode = 'estimated'
        self.workcenter.costs_hour = 33
        self.workcenter.employee_costs_hour = 60
        self.mo.action_confirm()

        self.mo.workorder_ids.duration = 10
        self.assertEqual(self.mo.workorder_ids._cal_cost(), 93.0)

        # Cost should stay the same for a done MO if nothing else is changed
        self.mo.button_mark_done()
        self.bom.operation_ids.cost_mode = 'actual'
        self.workcenter.employee_costs_hour = 99
        self.assertEqual(self.mo.workorder_ids._cal_cost(), 93.0)

    @users('test_without_hr_right')
    def test_create_workorder_without_hr_right(self):
        self.env['mrp.workorder'].create({
            'name': 'Test work order',
            'workcenter_id': self.workcenter.id,
            'production_id': self.mo.id,
            'employee_assigned_ids': self.employee_1.ids,
        })

    @users('test_without_hr_right')
    def test_create_manufacturing_order_without_hr_right(self):
        production = self.env['mrp.production'].create({
            'bom_id': self.bom.id,
            'product_qty': 1,
            'workorder_ids': [Command.create({
                'name': 'Test work order',
                'workcenter_id': self.workcenter.id,
                'production_id': self.mo.id,
                'employee_assigned_ids': self.employee_1.ids,
                'employee_ids': self.employee_1.ids,
            })],
        })
        self.assertEqual(production.employee_ids, self.employee_1)

    @users('test_without_hr_right')
    def test_create_workcenter_without_hr_right(self):
        self.env['mrp.workcenter'].create({
            'name': 'Test Workcenter',
            'time_start': 10,
            'time_stop': 5,
            'employee_ids': self.employee_1.ids,
            'time_efficiency': 80,
        })
