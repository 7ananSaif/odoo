from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import fields
from odoo.fields import Command
from odoo.fields import Domain
from odoo.tools import float_compare
from odoo.exceptions import ValidationError

from odoo.addons.esg.tests.esg_common import TestEsgCommon


class TestEsgCarbonEmission(TestEsgCommon):

    def test_physical_method_other_emission_value(self):
        other_emission = self.env['esg.other.emission'].create({
            'name': 'Package Delivery',
            'date': fields.Date.today(),
            'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
            'uom_id': self.env.ref('uom.product_uom_mile').id,
            'quantity': 100,
        })
        self.assertEqual(other_emission.esg_emissions_value, 6.214)  # 100 (emission quantity) * 0.1 (factor value) * 0.6214 (km->mile conversion) = 6.214 kgCO2e
        self.assertEqual(other_emission.esg_uncertainty_absolute_value, 2.1749)  # 6.214 (emission value) * 0.35 (factor uncertainty) = 2.1749 kgCO2e
        # Change quantity
        other_emission.quantity = 200
        self.assertEqual(other_emission.esg_emissions_value, 12.428)  # 200 (emission quantity) * 0.1 (factor value) * 0.6214 (km->mile conversion) = 12.428 kgCO2e
        self.assertEqual(other_emission.esg_uncertainty_absolute_value, 4.3498)  # 12.428 (emission value) * 0.35 (factor uncertainty) = 2.1749 kgCO2e

    def test_monetary_method_other_emission_value(self):
        other_emission = self.env['esg.other.emission'].create({
            'name': 'Office Electricity',
            'date': fields.Date.today(),
            'esg_emission_factor_id': self.emission_factor_electricity_consumption.id,
            'currency_id': self.env.ref('base.EUR').id,
            'quantity': 150,
        })
        self.assertEqual(other_emission.esg_emissions_value, 1.5)  # 150 (emission quantity) * 0.01 (factor value) * 1.0 (EUR->EUR conversion) = 1.5 kgCO2e
        self.assertEqual(other_emission.esg_uncertainty_absolute_value, 0.375)  # 1.5 (emission value) * 0.25 (factor uncertainty) = 0.375 kgCO2e
        # Change quantity
        other_emission.quantity = 300
        self.assertEqual(other_emission.esg_emissions_value, 3)  # 300 (emission quantity) * 0.01 (factor value) * 1.0 (EUR->EUR conversion) = 3 kgCO2e
        self.assertEqual(other_emission.esg_uncertainty_absolute_value, 0.75)  # 3 (emission value) * 0.35 (factor uncertainty) = 0.75 kgCO2e

    def test_physical_method_account_move_line_emission_value(self):
        bill_line = self.env['account.move.line'].create({
            'move_id': self.bill_1.id,
            'name': 'Computer',
            'quantity': 50,
            'esg_emission_factor_id': self.emission_factor_computers_production.id,
            'product_uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        self.assertEqual(bill_line.esg_emissions_value, 4648.0)  # 50 (aml quantity) * 92.96 (factor value) * 1.0 (unit->unit conversion) = 4648 kgCO2e
        self.assertEqual(float_compare(bill_line.esg_uncertainty_absolute_value, 697.199, precision_rounding=3), 0)  # 4663.5 (emission value) * 0.15 (factor uncertainty) = 697.199 kgCO2e
        # Change quantity
        bill_line.quantity = 100
        self.assertEqual(bill_line.esg_emissions_value, 9296.0)  # 100 (aml quantity) * 92.96 (factor value) * 1.0 (unit->unit conversion) = 9296.0 kgCO2e
        self.assertEqual(float_compare(bill_line.esg_uncertainty_absolute_value, 1394.39, precision_rounding=2), 0)  # 9327 (emission value) * 0.15 (factor uncertainty) = 1394.39 kgCO2e

    def test_physical_method_account_move_line_emission_value_with_relative_uom(self):
        self.assertEqual(self.emission_factor_phones_production.uom_id, self.env.ref('uom.product_uom_unit'))
        bill_line_values = {
            'move_id': self.bill_1.id,
            'name': 'Computer',
            'quantity': 50,
            'esg_emission_factor_id': self.emission_factor_phones_production.id,
        }
        bill_line_1 = self.env['account.move.line'].create({
            **bill_line_values,
            'product_uom_id': self.env.ref('uom.product_uom_dozen').id,
        })
        self.assertEqual(bill_line_1.esg_emissions_value, 45000)  # 50 (aml quantity) * 75 (factor value) * 12.0 (pack of 12 units->unit conversion) = 45000 kgCO2e
        self.assertEqual(bill_line_1.esg_uncertainty_absolute_value, 11250)  # 45000 (emission value) * 0.25 (factor uncertainty) = 11250 kgCO2e

        # Inverse both uoms
        self.emission_factor_phones_production.uom_id = self.env.ref('uom.product_uom_dozen')
        bill_line_2 = self.env['account.move.line'].create({
            **bill_line_values,
            'product_uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        self.assertEqual(bill_line_2.esg_emissions_value, 312.5)  # 50 (aml quantity) * 75 (factor value) * 1/12.0 (unit->pack of 12 units conversion) = 312.5 kgCO2e
        self.assertEqual(bill_line_2.esg_uncertainty_absolute_value, 78.125)  # 312.5 (emission value) * 0.25 (factor uncertainty) = 78.125 kgCO2e

    def test_monetary_method_account_move_line_emission_value(self):
        for account, esg_usable in self.accounts_to_esg_usable.items():
            # Test with all usable account types and a non-usable one.
            with self.subTest(account=account, esg_usable=esg_usable):
                bill_line = self.env['account.move.line'].create({
                    'move_id': self.bill_1.id,
                    'name': 'Foreign Electricity Consumption',
                    'price_unit': 100.0,
                    'esg_emission_factor_id': self.emission_factor_foreign_electricity_consumption.id,
                    'account_id': account.id,
                })
                conversion_rate = self.emission_factor_foreign_electricity_consumption.currency_id._convert(1, bill_line.currency_id, date=bill_line.date)
                self.assertEqual(bill_line.esg_emissions_value * conversion_rate, 5.0 if esg_usable else 0)  # 100.0 (aml price) * 0.05 (factor value) * (USD->EUR conversion) = 5 * (USD->EUR conversion) kgCO2e
                self.assertEqual(bill_line.esg_uncertainty_absolute_value, 2.25 if esg_usable else 0)  # 5.0 (emission value) * 0.45 (factor uncertainty) = 2.25 kgCO2e
                # Change price
                bill_line.price_unit = 200.0
                self.assertEqual(bill_line.esg_emissions_value * conversion_rate, 10.0 if esg_usable else 0)  # 200.0 (aml price) * 0.05 (factor value) * (USD->EUR conversion) = 10 * (USD->EUR conversion) kgCO2e
                self.assertEqual(bill_line.esg_uncertainty_absolute_value, 4.5 if esg_usable else 0)  # 10.0 (emission value) * 0.45 (factor uncertainty) = 4.5 kgCO2e

    def test_compute_method_other_emission(self):
        other_emission = self.env['esg.other.emission'].create({
            'name': 'Package Delivery',
            'date': fields.Date.today(),
            'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
            'quantity': 100,
        })
        self.assertEqual(other_emission.compute_method, 'physically', 'The compute method of the emission should be the same as the emission factor')
        self.assertEqual(other_emission.uom_id, self.env.ref('uom.product_uom_km'), 'The default UoM should be the same as the emission factor')
        other_emission.esg_emission_factor_id = self.emission_factor_electricity_consumption.id
        self.assertFalse(other_emission.uom_id, 'The UoM should be empty as the compute method has changed')
        self.assertEqual(other_emission.compute_method, 'monetary', 'The compute method of the emission should be the same as the emission factor')
        self.assertEqual(other_emission.currency_id, self.env.ref('base.EUR'), 'The default currency should be the same as the emission factor')

    def test_gas_multiplicator_value_account_move_line(self):
        for account, esg_usable in self.accounts_to_esg_usable.items():
            # Test with all usable account types and a non-usable one.
            with self.subTest(account=account, esg_usable=esg_usable):
                bill_line = self.env['account.move.line'].create({
                    'move_id': self.bill_1.id,
                    'name': 'Computer',
                    'quantity': 50,
                    'esg_emission_factor_id': self.emission_factor_phones_production.id,
                    'product_uom_id': self.env.ref('uom.product_uom_unit').id,
                    'account_id': account.id,
                })
                # Test on physical compute method
                self.assertEqual(bill_line.esg_emission_multiplicator, 50 if esg_usable else 0)  # 50 (aml quantity) * 1.0 (unit->unit conversion) = 50
                self.assertEqual(bill_line.esg_emissions_value, 3750 if esg_usable else 0)  # 50 (gas multiplicator) * 75 (factor value) = 3750 kgCO2e
                bill_line.quantity = 100
                self.assertEqual(bill_line.esg_emission_multiplicator, 100 if esg_usable else 0, 'The gas multiplicator should have doubled')
                self.assertEqual(bill_line.esg_emissions_value, 7500 if esg_usable else 0, 'The emissions value should have doubled too')

                # Remove the emission factor from the bill line
                bill_line.esg_emission_factor_id = False
                self.assertEqual(bill_line.esg_emission_multiplicator, 0, 'The gas multiplicator should be 0 as the emission factor is empty')
                self.assertEqual(bill_line.esg_emissions_value, 0, 'The emissions value should be 0 as the emission factor is empty')

                # Add a new emission factor to the bill line: test on monetary compute method
                bill_line.esg_emission_factor_id = self.emission_factor_electricity_consumption
                self.assertEqual(bill_line.esg_emission_multiplicator, 0, 'The gas multiplicator should be 0 as the amount is 0')
                self.assertEqual(bill_line.esg_emissions_value, 0, 'The emissions value should be 0 as the amount is 0')
                bill_line.price_unit = 5
                self.assertEqual(bill_line.price_subtotal, 500)  # price_subtotal = 5 * 100 (quantity) = 500 EUR
                self.assertEqual(bill_line.esg_emission_multiplicator, 500 if esg_usable else 0)  # 500 (aml price_subtotal) * 1.0 (EUR->EUR conversion) = 500
                self.assertEqual(bill_line.esg_emissions_value, 5 if esg_usable else 0)  # 500 (gas multiplicator) * 0.01 (factor value) = 5 kgCO2e
                bill_line.price_unit = 10
                self.assertEqual(bill_line.price_subtotal, 1000)  # price_subtotal = 10 * 100 (quantity) = 1000 EUR
                self.assertEqual(bill_line.esg_emission_multiplicator, 1000 if esg_usable else 0, 'The gas multiplicator should have doubled')
                self.assertEqual(bill_line.esg_emissions_value, 10 if esg_usable else 0, 'The emissions value should have doubled too')

                # Switch back to physical compute method
                bill_line.esg_emission_factor_id = self.emission_factor_phones_production
                self.assertEqual(bill_line.esg_emission_multiplicator, 100 if esg_usable else 0, 'The gas multiplicator should have been recomputed')
                self.assertEqual(bill_line.esg_emissions_value, 7500 if esg_usable else 0, 'The emissions value should have been recomputed')

    def test_gas_multiplicator_value_other_emission(self):
        other_emission = self.env['esg.other.emission'].create({
            'name': 'Package Delivery',
            'date': fields.Date.today(),
            'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
            'quantity': 150,
            'uom_id': self.env.ref('uom.product_uom_km').id,
        })
        # Test on physical compute method
        self.assertEqual(other_emission.esg_emission_multiplicator, 150)  # 150 (emission quantity) * 1.0 (km->km conversion) = 150
        self.assertEqual(other_emission.esg_emissions_value, 15)  # 150 (gas multiplicator) * 0.1 (factor value) = 15 kgCO2e
        other_emission.quantity = 300
        self.assertEqual(other_emission.esg_emission_multiplicator, 300, 'The gas multiplicator should have doubled')
        self.assertEqual(other_emission.esg_emissions_value, 30, 'The emissions value should have doubled too')

        # Remove the emission factor from the other emission
        other_emission.esg_emission_factor_id = False
        self.assertEqual(other_emission.esg_emission_multiplicator, 0, 'The gas multiplicator should be 0 as the emission factor is empty')
        self.assertEqual(other_emission.esg_emissions_value, 0, 'The emissions value should be 0 as the emission factor is empty')

        # Add a new emission factor to the other emission: test on monetary compute method
        other_emission.currency_id = self.env.ref('base.EUR')
        other_emission.esg_emission_factor_id = self.emission_factor_electricity_consumption
        self.assertEqual(other_emission.esg_emission_multiplicator, 300)  # 300 (emission quantity) * 1.0 (EUR->EUR conversion) = 300
        self.assertEqual(other_emission.esg_emissions_value, 3)  # 300 (gas multiplicator) * 0.01 (factor value) = 3 kgCO2e
        other_emission.quantity = 600
        self.assertEqual(other_emission.esg_emission_multiplicator, 600, 'The gas multiplicator should have doubled')
        self.assertEqual(other_emission.esg_emissions_value, 6, 'The emissions value should have doubled too')

        # Switch back to physical compute method
        other_emission.esg_emission_factor_id = self.emission_factor_delivery_transportation
        self.assertEqual(other_emission.esg_emission_multiplicator, 600, 'The gas multiplicator should have been recomputed')  # 600 (emission quantity) * 1.0 (km->km conversion) = 600
        self.assertEqual(other_emission.esg_emissions_value, 60, 'The emissions value should have been recomputed')  # 600 (gas multiplicator) * 0.1 (factor value) = 60 kgCO2e

    def test_auto_assign_factor_to_account_move_line_case_1(self):
        # Assignation rule 1 and 2
        for account, esg_usable in self.accounts_to_esg_usable.items():
            # Test with all usable account types and a non-usable one.
            with self.subTest(account=account, esg_usable=esg_usable):
                create_values = [
                    {
                        'product_id': self.product_a.id,
                        'partner_id': self.partner_a.id,
                        'account_id': account.id,
                        'esg_emission_factor_id': self.emission_factor_computers_production.id,
                    },
                    {
                        'product_id': self.product_b.id,
                        'partner_id': self.partner_a.id,
                        'account_id': account.id,
                        'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
                    },
                ]
                if not esg_usable:
                    with self.assertRaises(ValidationError, msg='The account should have a valid type for ESG assignation rules'):
                        self.env['esg.assignation.line'].create(create_values)
                else:
                    self.env['esg.assignation.line'].create(create_values)
                    bill_line = self.env['account.move.line'].create({
                        'move_id': self.bill_1.id,
                        'product_id': self.product_b.id,
                        'account_id': account.id,
                    })
                    self.assertEqual(
                        bill_line.esg_emission_factor_id,
                        self.emission_factor_delivery_transportation if esg_usable else self.env['esg.emission.factor'],
                        'The assignation rule 2 matches the most criteria, so it should be used to assign this emission factor to the move line',
                    )

    def test_auto_assign_factor_to_account_move_line_case_2(self):
        # Assignation rule 1 and 2
        self.env['esg.assignation.line'].create([
            {
                'partner_id': self.partner_a.id,
                'esg_emission_factor_id': self.emission_factor_computers_production.id,
            },
            {
                'product_id': self.product_b.id,
                'partner_id': self.partner_b.id,
                'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
            },
        ])
        bill_line = self.env['account.move.line'].create({
            'move_id': self.bill_1.id,
            'product_id': self.product_b.id,
        })
        self.assertEqual(
            bill_line.esg_emission_factor_id,
            self.emission_factor_computers_production,
            'The assignation rule 1 matches the most criteria, so it should be used to assign this emission factor to the move line',
        )

    def test_auto_assign_factor_to_account_move_line_case_3(self):
        # Assignation rule 1 and 2
        self.env['esg.assignation.line'].create([{
            'product_id': self.product_a.id,
            'esg_emission_factor_id': self.emission_factor_computers_production.id,
        }])
        for account, esg_usable in self.accounts_to_esg_usable.items():
            # Test with all usable account types and a non-usable one.
            with self.subTest(account=account, esg_usable=esg_usable):
                create_values = {
                    'partner_id': self.partner_a.id,
                    'account_id': account.id,
                    'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
                }
                if not esg_usable:
                    with self.assertRaises(ValidationError, msg='The account should have a valid type for ESG assignation rules'):
                        self.env['esg.assignation.line'].create(create_values)
                else:
                    self.env['esg.assignation.line'].create(create_values)
                    bill_line = self.env['account.move.line'].create({
                        'move_id': self.bill_1.id,
                        'product_id': self.product_a.id,
                        'account_id': account.id,
                    })
                    self.assertEqual(
                        bill_line.esg_emission_factor_id,
                        self.emission_factor_computers_production if esg_usable else self.env['esg.emission.factor'],
                        'The assignation rule 1 matches the most important criteria (product > partner > account), so it should be used to assign this emission factor to the move line',
                    )

    def test_auto_assign_factor_to_account_move_line_change_product(self):
        # Assignation rule 1 and 2
        self.env['esg.assignation.line'].create([
            {
                'product_id': self.product_a.id,
                'esg_emission_factor_id': self.emission_factor_computers_production.id,
            },
            {
                'product_id': self.product_b.id,
                'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
            },
        ])
        bill_line = self.env['account.move.line'].create({
            'move_id': self.bill_1.id,
            'product_id': self.product_a.id,
        })
        self.assertEqual(
            bill_line.esg_emission_factor_id,
            self.emission_factor_computers_production,
            'The assignation rule 1 matches the product, so it should be used to assign this emission factor to the move line',
        )
        bill_line.product_id = self.product_b.id
        self.assertEqual(
            bill_line.esg_emission_factor_id,
            self.emission_factor_delivery_transportation,
            'The assignation rule 2 matches the product, so it should be used to assign this emission factor to the move line',
        )
        bill_line.product_id = self.product.id
        self.assertFalse(
            bill_line.esg_emission_factor_id,
            'No assignation rule matches the product, so the emission factor should be empty',
        )

    @freeze_time('2024-12-31')
    def test_apply_factors_auto_assignment_wizard(self):
        self.bill_1.date = fields.Date.today() - relativedelta(days=15)
        # bill_line_1 & bill_line_2 -> with factor
        # bill_line_3 & bill_line_4 -> without factor
        bill_line_1, bill_line_2, bill_line_3, bill_line_4 = self.env['account.move.line'].create([
            {
                'move_id': self.bill_1.id,
                'product_id': self.product_a.id,
                'price_unit': 250.0,
                'account_id': self.expense_account.id,
            },
            {
                'move_id': self.bill_1.id,
                'product_id': self.product_b.id,
                'price_unit': 150.0,
                'account_id': self.expense_account.id,
            },
            {
                'move_id': self.bill_1.id,
                'product_id': self.product_a.id,
                'quantity': 50,
                'account_id': self.expense_account.id,
                'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
            },
            {
                'move_id': self.bill_1.id,
                'product_id': self.product_b.id,
                'quantity': 200,
                'account_id': self.expense_account.id,
                'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
            },
        ])

        # Add an assignation rule
        assignation_line = self.env['esg.assignation.line'].create({
            'product_id': self.product_a.id,
            'esg_emission_factor_id': self.emission_factor_computers_production.id,
        })

        # Run the factor rule matching with factor replacement not allowed
        self.env['factors.auto.assignment.wizard'].with_context(active_ids=self.emission_factor_computers_production.ids).create({
            'start_date': fields.Date.today() - relativedelta(days=30),
            'end_date': fields.Date.today(),
            'replace_previous_factors': False,
        }).action_save()
        self.assertEqual(
            bill_line_1.esg_emission_factor_id,
            self.emission_factor_computers_production,
            'The assignation rule matches the product, so it should be used to assign this emission factor to the move line',
        )
        self.assertFalse(
            bill_line_2.esg_emission_factor_id,
            'The assignation rule does not match the product, so the emission factor should be empty',
        )
        self.assertEqual(
            bill_line_3.esg_emission_factor_id,
            self.emission_factor_delivery_transportation,
            'As this bill line already has a factor, it should not be replaced by the assignation rule',
        )
        self.assertEqual(
            bill_line_4.esg_emission_factor_id,
            self.emission_factor_delivery_transportation,
            'As this bill line already has a factor and does not match, it should not be replaced by the assignation rule',
        )

        bill_line_1.esg_emission_factor_id = False  # Reset the factor of the first bill line
        # Run the factor rule matching with factor replacement allowed
        self.env['factors.auto.assignment.wizard'].with_context(active_ids=self.emission_factor_computers_production.ids).create({
            'start_date': fields.Date.today() - relativedelta(days=30),
            'end_date': fields.Date.today(),
            'replace_previous_factors': True,
        }).action_save()
        self.assertEqual(
            bill_line_1.esg_emission_factor_id,
            self.emission_factor_computers_production,
            'The assignation rule matches the product, so it should be used to assign this emission factor to the move line',
        )
        self.assertFalse(
            bill_line_2.esg_emission_factor_id,
            'The assignation rule still does not match the product, so the emission factor should still be empty',
        )
        self.assertEqual(
            bill_line_3.esg_emission_factor_id,
            self.emission_factor_computers_production,
            'Even if this bill line already had a factor, it should be replaced by the assignation rule',
        )
        self.assertEqual(
            bill_line_4.esg_emission_factor_id,
            self.emission_factor_delivery_transportation,
            'As this bill line does not match, it should not be replaced by the assignation rule',
        )

        # Change the assignation rule
        assignation_line.product_id = self.product_b.id
        # Run the factor rule matching with factor replacement allowed
        self.env['factors.auto.assignment.wizard'].with_context(active_ids=self.emission_factor_computers_production.ids).create({
            'start_date': fields.Date.today() - relativedelta(days=30),
            'end_date': fields.Date.today(),
            'replace_previous_factors': True,
        }).action_save()
        self.assertFalse(
            bill_line_1.esg_emission_factor_id,
            'The assignation rule does not match the product anymore, so the emission factor should be empty',
        )
        self.assertEqual(
            bill_line_2.esg_emission_factor_id,
            self.emission_factor_computers_production,
            'The assignation rule matches the product, so it should be used to assign this emission factor to the move line',
        )
        self.assertFalse(
            bill_line_3.esg_emission_factor_id,
            'The assignation rule does not match the product anymore, so the emission factor should be empty',
        )
        self.assertEqual(
            bill_line_4.esg_emission_factor_id,
            self.emission_factor_computers_production,
            'The assignation rule matches the product, so it should be used to assign this emission factor to the move line',
        )

    def test_auto_generate_assignation_rules(self):
        bill_line_1, bill_line_2, bill_line_3, bill_line_4 = self.env['account.move.line'].with_context(auto_generate_esg_assignation_rule=False).create([
            {
                'move_id': self.bill_1.id,
                'product_id': self.product_a.id,
                'price_unit': 250.0,
                'account_id': self.expense_account.id,
            },
            {
                'move_id': self.bill_1.id,
                'product_id': self.product_b.id,
                'price_unit': 150.0,
                'account_id': self.expense_account.id,
            },
            {
                'move_id': self.bill_1.id,
                'product_id': self.product_a.id,
                'quantity': 50,
                'account_id': self.expense_account.id,
                'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
            },
            {
                'move_id': self.bill_1.id,
                'product_id': self.product_b.id,
                'quantity': 200,
                'account_id': self.expense_account.id,
                'esg_emission_factor_id': self.emission_factor_delivery_transportation.id,
            },
        ]).with_context(auto_generate_esg_assignation_rule=True)
        emission_factors = self.emission_factor_delivery_transportation + self.emission_factor_electricity_consumption + self.emission_factor_computers_production
        esg_assignation_rules_domain = Domain('esg_emission_factor_id', 'in', emission_factors.ids)
        assignation_rules = self.env['esg.assignation.line'].search(esg_assignation_rules_domain)
        self.assertFalse(assignation_rules, "No rule should exist for the emission factors selected for the test.")
        bill2 = self.bill_1.copy({'line_ids': []})
        _bill2_line_1, bill2_line_2, _bill2_line_3, bill2_line_4 = (bill_line_1 + bill_line_2 + bill_line_3 + bill_line_4).with_context(auto_generate_esg_assignation_rule=True).copy({'move_id': bill2.id})
        assignation_rules = self.env['esg.assignation.line'].search(esg_assignation_rules_domain)
        self.assertEqual(len(assignation_rules), 2, "2 rules should have been created for the emission factors used on the bill lines.")
        for rule in assignation_rules:
            self.assertEqual(rule.esg_emission_factor_id, self.emission_factor_delivery_transportation)
            self.assertEqual(rule.partner_id, self.bill_1.partner_id)
            self.assertEqual(rule.account_id, self.expense_account)
        rule1, rule2 = assignation_rules
        self.assertEqual(rule1.product_id, bill_line_3.product_id)
        self.assertEqual(rule2.product_id, bill_line_4.product_id)

        bill2_line_4.esg_emission_factor_id = self.emission_factor_computers_production
        assignation_rules = self.env['esg.assignation.line'].search(esg_assignation_rules_domain)
        self.assertEqual(len(assignation_rules), 1, "1 rule should exist, one should be removed since the rule has been breaking because of the changes on the AML.")
        self.assertEqual(assignation_rules, rule1, "The remaining rule should be the one checked.")
        bill2_line_4.account_id = self.expense_direct_cost_account
        bill2_line_4.esg_emission_factor_id = self.emission_factor_delivery_transportation
        assignation_rules = self.env['esg.assignation.line'].search(esg_assignation_rules_domain)
        self.assertEqual(len(assignation_rules), 2, "2 rules should have been created for the emission factors used on the bill lines.")
        for rule in assignation_rules:
            self.assertEqual(rule.esg_emission_factor_id, self.emission_factor_delivery_transportation)
            self.assertEqual(rule.partner_id, self.bill_1.partner_id)
        rule1, rule2 = assignation_rules
        self.assertEqual(rule1.product_id, bill_line_3.product_id)
        self.assertEqual(rule1.account_id, self.expense_account)
        self.assertFalse(rule2.product_id)
        self.assertFalse(rule2.account_id)
        (bill_line_2 + bill2_line_2).write({'esg_emission_factor_id': self.emission_factor_delivery_transportation.id})
        assignation_rules = self.env['esg.assignation.line'].search(esg_assignation_rules_domain)
        self.assertEqual(len(assignation_rules), 3, "3 rules should have been created for the emission factors used on the bill lines.")
        for rule in assignation_rules:
            self.assertEqual(rule.partner_id, self.bill_1.partner_id)
            self.assertEqual(rule.partner_id, self.bill_1.partner_id)
            self.assertEqual(rule.partner_id, self.bill_1.partner_id)
        rule1, rule2, rule3 = assignation_rules
        self.assertEqual(rule1.product_id, self.product_a)
        self.assertFalse(rule2.product_id)
        self.assertEqual(rule3.product_id, self.product_b)
        self.assertEqual(rule1.account_id, self.expense_account)
        self.assertFalse(rule2.account_id)
        self.assertEqual(rule3.account_id, self.expense_account)

    def test_auto_generate_assignation_rules_when_2_fields_common(self):
        partner_c = self.env['res.partner'].create({'name': 'Partner C'})
        self.bill_1.copy({'line_ids': [Command.create({'product_id': self.product_b.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_computers_production.id})], 'partner_id': self.partner_b.id})
        self.bill_1.copy({'line_ids': [Command.create({'product_id': self.product_b.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_computers_production.id})], 'partner_id': partner_c.id})
        assignation_rules_domain = [
            ('esg_emission_factor_id', 'in', (self.emission_factor_delivery_transportation + self.emission_factor_computers_production).ids)
        ]
        self.assertFalse(self.env['esg.assignation.line'].search(assignation_rules_domain), "No rule should exist for the emission factors selected for the test.")
        self.env['account.move.line'].create([
            {'move_id': self.bill_1.id, 'product_id': self.product_a.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_a.id, 'account_id': self.expense_direct_cost_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_a.id, 'account_id': self.expense_other_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_b.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_computers_production.id},
        ])
        assignation_rules = self.env['esg.assignation.line'].search(assignation_rules_domain)
        self.assertEqual(len(assignation_rules), 2, "2 rules should have been created")
        rule1, rule2 = assignation_rules
        self.assertEqual(rule1.esg_emission_factor_id, self.emission_factor_delivery_transportation)
        self.assertEqual(rule1.partner_id, self.partner_a)
        self.assertEqual(rule1.product_id, self.product_a)
        self.assertFalse(rule1.account_id)
        self.assertEqual(rule2.esg_emission_factor_id, self.emission_factor_computers_production)
        self.assertFalse(rule2.partner_id)
        self.assertEqual(rule2.product_id, self.product_b)
        self.assertEqual(rule2.account_id, self.expense_account)

    def test_auto_generate_assignation_rules_when_partner_in_common(self):
        assignation_rules_domain = [
            ('esg_emission_factor_id', '=', self.emission_factor_delivery_transportation.id),
        ]
        self.assertFalse(self.env['esg.assignation.line'].search(assignation_rules_domain), "No rule should exist for the emission factors selected for the test.")
        self.env['account.move.line'].create([
            {'move_id': self.bill_1.id, 'product_id': self.product_a.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_b.id, 'account_id': self.expense_direct_cost_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_a.id, 'account_id': self.expense_other_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_b.id, 'account_id': self.asset_fixed_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
        ])
        assignation_rules = self.env['esg.assignation.line'].search(assignation_rules_domain)
        self.assertEqual(len(assignation_rules), 1, "1 rules should have been created")
        rule = assignation_rules
        self.assertEqual(rule.esg_emission_factor_id, self.emission_factor_delivery_transportation)
        self.assertEqual(rule.partner_id, self.partner_a)
        self.assertFalse(rule.product_id)
        self.assertFalse(rule.account_id)

    def test_auto_generate_assignation_rules_when_product_in_common(self):
        partner_c = self.env['res.partner'].create({'name': 'Partner C'})
        self.bill_1.copy({'line_ids': [Command.create({'product_id': self.product_a.id, 'account_id': self.expense_other_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id})], 'partner_id': self.partner_b.id})
        self.bill_1.copy({'line_ids': [Command.create({'product_id': self.product_a.id, 'account_id': self.expense_direct_cost_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id})], 'partner_id': partner_c.id})
        assignation_rules_domain = [
            ('esg_emission_factor_id', 'in', (self.emission_factor_delivery_transportation + self.emission_factor_computers_production).ids)
        ]
        self.assertFalse(self.env['esg.assignation.line'].search(assignation_rules_domain), "No rule should exist for the emission factors selected for the test.")
        self.env['account.move.line'].create([
            {'move_id': self.bill_1.id, 'product_id': self.product_a.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_a.id, 'account_id': self.expense_direct_cost_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
        ])
        assignation_rules = self.env['esg.assignation.line'].search(assignation_rules_domain)
        self.assertEqual(len(assignation_rules), 1, "1 rule should have been created")
        rule = assignation_rules
        self.assertEqual(rule.esg_emission_factor_id, self.emission_factor_delivery_transportation)
        self.assertFalse(rule.partner_id)
        self.assertEqual(rule.product_id, self.product_a)
        self.assertFalse(rule.account_id)

    def test_auto_generate_assignation_rules_when_account_in_common(self):
        partner_c = self.env['res.partner'].create({'name': 'Partner C'})
        self.bill_1.copy({'line_ids': [Command.create({'product_id': self.product_b.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id})], 'partner_id': self.partner_b.id})
        self.bill_1.copy({'line_ids': [Command.create({'product_id': self.product_a.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id})], 'partner_id': partner_c.id})
        assignation_rules_domain = [
            ('esg_emission_factor_id', 'in', (self.emission_factor_delivery_transportation + self.emission_factor_computers_production).ids)
        ]
        self.assertFalse(self.env['esg.assignation.line'].search(assignation_rules_domain), "No rule should exist for the emission factors selected for the test.")
        self.env['account.move.line'].create([
            {'move_id': self.bill_1.id, 'product_id': self.product_a.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_b.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
        ])
        assignation_rules = self.env['esg.assignation.line'].search(assignation_rules_domain)
        self.assertEqual(len(assignation_rules), 1, "1 rule should have been created")
        rule = assignation_rules
        self.assertEqual(rule.esg_emission_factor_id, self.emission_factor_delivery_transportation)
        self.assertFalse(rule.partner_id)
        self.assertFalse(rule.product_id)
        self.assertEqual(rule.account_id, self.expense_account)

    def test_no_auto_generate_assignation_rules_on_copy(self):
        assignation_rules_domain = [
            ('esg_emission_factor_id', '=', self.emission_factor_delivery_transportation.id),
        ]
        self.assertFalse(self.env['esg.assignation.line'].search(assignation_rules_domain), "No rule should exist for the emission factors selected for the test.")
        self.env['account.move.line'].create([
            {'move_id': self.bill_1.id, 'product_id': self.product_a.id, 'account_id': self.expense_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_b.id, 'account_id': self.expense_direct_cost_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_a.id, 'account_id': self.expense_other_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
            {'move_id': self.bill_1.id, 'product_id': self.product_b.id, 'account_id': self.asset_fixed_account.id, 'esg_emission_factor_id': self.emission_factor_delivery_transportation.id},
        ])
        assignation_rules = self.env['esg.assignation.line'].search(assignation_rules_domain)
        self.assertEqual(len(assignation_rules), 1, "1 rules should have been created")
        self.bill_1.copy()
        assignation_rules = self.env['esg.assignation.line'].search(assignation_rules_domain)
        self.assertEqual(len(assignation_rules), 1, "No new rules should have been created")
