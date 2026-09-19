# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time

from odoo.addons.mrp_account.tests.test_valuation_layers import TestMrpValuationCommon
from odoo.fields import Command
from odoo.tests import Form, tagged

from datetime import datetime, timedelta


class TestMrpWorkorderHrValuation(TestMrpValuationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        grp_workorder = cls.env.ref('mrp.group_mrp_routings')
        cls.env.user.write({'group_ids': [(4, grp_workorder.id)]})
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Jean Michel',
            'hourly_cost': 100,
        })

        cls.employee_center = cls.env['mrp.workcenter'].create({
            'name': 'Jean Michel\'s Center',
            'costs_hour': 10,
            'employee_ids': [(4, cls.employee.id)],
        })

        cls.bom.operation_ids = [(0, 0, {
            'name': 'Super Operation',
            'workcenter_id': cls.employee_center.id,
            'time_mode': 'manual',
            'time_cycle_manual': 60,
        })]

    def test_workcenter_employee_cost_impacting_on_valuation(self):
        """
            When the employee's *cost per hour* is set on the employee's form, it
            must override the workcenter's *employee cost per hour* for AVCO/FIFO
            products. However, if the employee's cost per hour is zero, then the
            workcenter's employee cost per hour should be used on valuations.
        """
        def produce():
            mo_form = Form(self.env['mrp.production'])
            mo_form.bom_id = self.bom
            mo = mo_form.save()
            mo.action_confirm()

            with Form(mo) as mo_form:
                mo_form.qty_producing = 1

            # Register a productivity of one hour
            now = datetime.now()
            workorder = mo.workorder_ids
            productivity = self.env['mrp.workcenter.productivity'].create({
                'employee_id': self.employee.id,
                'workcenter_id': self.employee_center.id,
                'workorder_id': workorder.id,
                'date_start': now,
                'date_end': now + timedelta(hours=1),
                'loss_id': self.env.ref('mrp.block_reason7').id,
            })
            workorder.button_finish()
            mo.button_mark_done()

            return mo, productivity

        def assert_employee_cost(expected_employee_cost):
            self.assertEqual(mo.move_finished_ids.stock_valuation_layer_ids.remaining_value, 10 + expected_employee_cost, f'Workcenter cost (10) + Employee cost ({expected_employee_cost})')
            self.assertEqual(mo.move_finished_ids.stock_valuation_layer_ids.unit_cost, 10 + expected_employee_cost, f'Workcenter cost (10) + Employee cost ({expected_employee_cost})')

        self.employee_center.employee_costs_hour = 50

        # 1) cost_method: fifo
        self.product1.categ_id.property_cost_method = 'fifo'

        # 1.1) hourly_cost set on employee's form
        self.employee.hourly_cost = 100
        mo, _ = produce()
        assert_employee_cost(100)

        # 1.2) hourly_cost not set on employee's form
        self.employee.hourly_cost = 0
        mo, _ = produce()
        assert_employee_cost(50) # must use workcenter's costs_hour

        # 2) cost_method: avco
        self.product1.categ_id.property_cost_method = 'average'

        # 2.1) hourly_cost set on employee's form
        self.employee.hourly_cost = 100
        mo, _ = produce()
        assert_employee_cost(100)

        # 2.2) hourly_cost not set on employee's form
        self.employee.hourly_cost = 0
        mo, _ = produce()
        assert_employee_cost(50) # must use workcenter's costs_hour

        # 3) changing employee cost after done the MO
        self.product1.categ_id.property_cost_method = 'average'
        self.employee.hourly_cost = 100
        mo, productivity = produce()
        self.assertEqual(mo.state, 'done')
        self.assertEqual(productivity.employee_cost, 100)
        self.assertEqual(productivity.total_cost, 100)
        self.employee.hourly_cost = 50
        self.assertEqual(productivity.employee_cost, 100, 'The productivity employee cost must remain unchanged after done the MO')
        self.assertEqual(productivity.total_cost, 100, 'Productivity time cost must remain unchanged after done the MO')

    @freeze_time('2020-01-01 08:00:00')
    def test_cost_calculation_multiple_employees_same_workcenter(self):
        self.product1.categ_id.property_cost_method = 'average'
        self.product1.standard_price = 75
        self.employee_center.costs_hour = 35
        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = self.bom
        mo = mo_form.save()
        mo.action_confirm()

        with Form(mo) as mo_form:
            mo_form.qty_producing = 1

        employee1, employee2 = self.employee, self.env['hr.employee'].create({
            'name': 'employee 2',
            'hourly_cost': 40
        })
        employee1.hourly_cost = 15
        workorder = mo.workorder_ids
        ymd = {'year': 2020, 'month': 1, 'day': 1}
        # emp1 works (08:00 until 09:30) and (11:30 until 12:00)
        self.env['mrp.workcenter.productivity'].create([{
            'employee_id': employee1.id,
            'workcenter_id': self.employee_center.id,
            'workorder_id': workorder.id,
            'date_start': start,
            'date_end': end,
            'loss_id': self.ref('mrp.block_reason7'),
        } for start, end in (
            (datetime(**ymd, hour=8), datetime(**ymd, hour=9, minute=30)),
            (datetime(**ymd, hour=11, minute=30), datetime(**ymd, hour=12)),
        )])
        # emp2 works (08:30:00 until 09:30) and (10:30 until 11:30)
        self.env['mrp.workcenter.productivity'].create([{
            'employee_id': employee2.id,
            'workcenter_id': self.employee_center.id,
            'workorder_id': workorder.id,
            'date_start': start,
            'date_end': end,
            'loss_id': self.ref('mrp.block_reason7'),
        } for start, end in (
            (datetime(**ymd, hour=8, minute=30), datetime(**ymd, hour=9, minute=30)),
            (datetime(**ymd, hour=10, minute=30), datetime(**ymd, hour=11, minute=30)),
        )])
        # => workcenter is operated from: [08:00 - 09:30] and [10:30 - 12:00] = 180 minutes
        # we should get a workcenter cost like: ($35 / hour * 1.5 hours) + ($35 / hour * 1.5 hours) = $105.0
        workorder.button_finish()
        mo.button_mark_done()
        finished_product_svl = self.env['stock.valuation.layer'].search([('product_id', '=', self.product1.id)])
        # SVL value derived like:
        #   emp1 total cost        + emp2 total cost        + workcenter costs
        # = ($15 / hour * 2 hours) + ($40 / hour * 2 hours) + ($105.0)
        # = $215.0
        self.assertRecordValues(
            finished_product_svl,
            [{'value': 215.0}],
        )


@tagged('post_install', '-at_install')
class TestMrpWorkorderHrValuationPostInstall(TestMrpValuationCommon):
    """
    Some tests rely on accounting operations. However, the Chart of Accounts is created
    only after all modules were loaded. Therefore, these tests need to be post_install.
    """
    def test_wip_accounting_01(self):
        """
        This test runs a WIP accounting for a workorder currently runnning.
        """
        self.env.user.write({'group_ids': [Command.link(self.ref('mrp.group_mrp_routings'))]})
        employee = self.env['hr.employee'].create({
            'name': 'Jean Michel',
            'hourly_cost': 100,
            'user_id': self.env.user.id,
        })
        employee_center = self.env['mrp.workcenter'].create({
            'name': 'Jean Michel\'s Center',
            'costs_hour': 10,
            'employee_ids': [Command.link(employee.id)],
        })
        bom_1 = self.env['mrp.bom'].create({
            'product_id': self.product1.id,
            'product_tmpl_id': self.product1.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({
                    'name': 'Fun Operation',
                    'workcenter_id': employee_center.id,
                    'time_mode': 'manual',
                    'time_cycle_manual': 20,
                    'sequence': 1,
                }),
            ],
        })

        with freeze_time('2027-09-01 10:00:00'):
            mo_form = Form(self.env['mrp.production'])
            mo_form.product_id = self.product1
            mo_form.bom_id = bom_1
            mo_form.product_qty = 1
            mo = mo_form.save()
        # post a WIP for a valid MO - no WO time completed, but time running, no valuated components consumed => nothing to debit/credit
        with freeze_time('2027-10-01 10:00:00'):
            mo.workorder_ids.button_start()
        with freeze_time('2027-10-01 10:30:00'):
            wizard = Form(self.env['mrp.account.wip.accounting'].with_context({'active_ids': [mo.id]}))
            wizard.save().confirm()
        wip_empty_entries = self.env['account.move'].search([('ref', 'ilike', 'WIP - ' + mo.name)])
        self.assertEqual(len(wip_empty_entries), 2, "Should be 2 journal entries: 1 for the WIP accounting + 1 for their reversals")
        self.assertEqual(wip_empty_entries[0].wip_production_count, 1, "WIP MOs should be linked to entries even if no 'done' work")
