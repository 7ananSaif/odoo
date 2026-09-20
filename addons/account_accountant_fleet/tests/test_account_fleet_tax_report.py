# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.addons.account.tests.test_account_move_line_tax_details import TestAccountTaxDetailsReport
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAccountFleet(TestAccountTaxDetailsReport):

    def test_tax_report_with_vehicle_split_repartition(self):
        """Test tax report with split repartition lines across different vehicles."""
        # Ensure user has access to fleet vehicles
        self.env.user.group_ids += self.env.ref('fleet.fleet_group_manager')
        brand = self.env["fleet.vehicle.model.brand"].create({"name": "Audi"})
        model = self.env["fleet.vehicle.model"].create({"brand_id": brand.id, "name": "A3"})
        cars = self.env["fleet.vehicle"].create([
            {"model_id": model.id, "plan_to_change_car": False},
            {"model_id": model.id, "plan_to_change_car": False},
        ])

        expense_account = self.company_data['default_account_expense']
        asset_account = self.company_data['default_account_deferred_expense']

        tax = self.env['account.tax'].create({
            'name': 'Split Tax',
            'amount': 10,
            'invoice_repartition_line_ids': [
                Command.create({'repartition_type': 'base', 'factor_percent': 100}),
                Command.create({'repartition_type': 'tax', 'factor_percent': 50, 'account_id': expense_account.id}),
                Command.create({'repartition_type': 'tax', 'factor_percent': 50, 'account_id': asset_account.id}),
            ],
            'refund_repartition_line_ids': [
                Command.create({'repartition_type': 'base', 'factor_percent': 100}),
                Command.create({'repartition_type': 'tax', 'factor_percent': 50, 'account_id': expense_account.id}),
                Command.create({'repartition_type': 'tax', 'factor_percent': 50, 'account_id': asset_account.id}),
            ],
        })

        bill = self.init_invoice('in_invoice', invoice_date='2025-10-16', post=False)
        bill.write({
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product_a.id,
                    'account_id': expense_account.id,
                    'price_unit': 100,
                    'tax_ids': [Command.set(tax.ids)],
                    'vehicle_id': cars[0].id
                }),
                Command.create({
                    'product_id': self.product_a.id,
                    'account_id': expense_account.id,
                    'price_unit': 100,
                    'tax_ids': [Command.set(tax.ids)],
                    'vehicle_id': cars[1].id
                }),
            ]
        })
        bill.action_post()

        tax_details = self._get_tax_details()
        self.assertEqual(len(tax_details), 2)
        for line in tax_details:
            self.assertEqual(line['tax_amount'], 5)
