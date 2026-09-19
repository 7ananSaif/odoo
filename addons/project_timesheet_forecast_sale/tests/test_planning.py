# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta, datetime

from odoo.tests import tagged

from odoo.addons.sale_planning.tests.common import TestCommonSalePlanning


@tagged('post_install', '-at_install')
class TestPlanning(TestCommonSalePlanning):

    def test_copy_previous_week_no_allocated_hours_project(self):
        project = self.env['project.project'].create({'name': 'Planning Project'})
        self.assertEqual(project.allocated_hours, 0)
        PlanningSlot = self.env['planning.slot']
        start = datetime(2019, 6, 25, 8, 0)
        slot = PlanningSlot.create({
            'start_datetime': start,
            'end_datetime': start + timedelta(hours=1),
            'project_id': project.id,
        })
        copy_start = start + timedelta(weeks=1)
        copy_domain = [('start_datetime', '=', copy_start), ('project_id', '=', project.id)]

        self.assertFalse(slot.was_copied)
        copy = PlanningSlot.search(copy_domain)
        self.assertEqual(len(copy), 0, "There should not be any slot at that time before the copy.")
        PlanningSlot.action_copy_previous_week(
            str(copy_start), [
                # dummy domain
                ('start_datetime', '=', True),
                ('end_datetime', '=', True),
            ]
        )
        self.assertTrue(slot.was_copied)
        copy = PlanningSlot.search(copy_domain)
        self.assertEqual(len(copy), 1, "The slot should have been copied as the project has no allocated hours.")

    def test_planning_analysis_sale_report_fields(self):
        ''' This test ensure that the fields of the planning analysis report are correctly computed'''
        so = self.env['sale.order'].create({
            "partner_id": self.planning_partner.id,
        })

        sol = self.env['sale.order.line'].create({
            "product_id": self.plannable_product.id,
            "product_uom_qty": 20,
            "order_id": so.id,
        })
        so.action_confirm()

        slot_1, slot_2 = self.env['planning.slot'].create([{
            'start_datetime': datetime(2025, 1, 22, 0, 0, 0),
            'end_datetime': datetime(2025, 1, 22, 12, 0, 0),
            'sale_line_id': sol.id,
            'resource_id': self.employee_wout.resource_id.id,
        }, {
            'start_datetime': datetime(2025, 1, 22, 12, 0, 0),
            'end_datetime': datetime(2025, 1, 22, 17, 0, 0),
            'resource_id': self.employee_wout.resource_id.id,
        }])

        report_values = self.env['planning.analysis.report']._read_group(
            [('slot_id', 'in', (slot_1.id, slot_2.id))],
            aggregates=['billable_allocated_hours:sum', 'non_billable_allocated_hours:sum'],
            groupby=['slot_id'],
        )

        expected_values = [
            (slot_1, 4.0, 0.0),
            (slot_2, 0.0, 4.0),
        ]

        self.assertListEqual(report_values, expected_values, "The report should be computed correctly")
