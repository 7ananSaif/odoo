from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestEsgCommon(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref('esg.esg_group_manager')

        cls.bill_1 = cls.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': cls.partner_a.id,
            'date': fields.Date.today(),
            'currency_id': cls.env.ref('base.EUR').id,
            'journal_id': cls.company_data['default_journal_purchase'].id,
        })

        cls.expense_account = cls.env.ref(f'account.{cls.env.company.id}_expense')
        cls.expense_direct_cost_account = cls.env.ref(f'account.{cls.env.company.id}_cost_of_goods_sold')
        cls.expense_other_account = cls.env['account.account'].create(
            {'name': "Other Expenses", 'code': '699999', 'account_type': 'expense_other'},
        )
        cls.asset_fixed_account = cls.env.ref(f'account.{cls.env.company.id}_fixed_assets')
        cls.current_assets_account = cls.env.ref(f'account.{cls.env.company.id}_current_assets')
        cls.accounts_to_esg_usable = {
            cls.expense_account: True,
            cls.expense_direct_cost_account: True,
            cls.expense_other_account: True,
            cls.asset_fixed_account: True,
            cls.current_assets_account: False,
        }

        cls.emission_source_direct = cls.env['esg.emission.source'].create({
            'name': 'Mobile Combustion',
            'scope': 'direct',
        })

        cls.emission_source_indirect = cls.env['esg.emission.source'].create({
            'name': 'Purchased Electricity',
            'scope': 'indirect',
        })

        cls.emission_source_upstream = cls.env['esg.emission.source'].create({
            'name': 'Purchased Goods and Services',
            'scope': 'indirect_others',
            'activity_flow_indirect_others': 'upstream',
        })

        cls.emission_source_downstream = cls.env['esg.emission.source'].create({
            'name': 'Downstream Transportation and Distribution',
            'scope': 'indirect_others',
            'activity_flow_indirect_others': 'downstream',
        })

        cls.emission_factor_computers_production = cls.env['esg.emission.factor'].create({
            'name': 'Computers (Hardware Equipment Production)',
            'source_id': cls.emission_source_upstream.id,
            'esg_uncertainty_value': 0.15,
            'compute_method': 'physically',
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
        })

        cls.computers_production_gas_lines = cls.env['esg.emission.factor.line'].create([
            {
                'gas_id': cls.env.ref('esg.esg_gas_co2').id,
                'esg_emission_factor_id': cls.emission_factor_computers_production.id,
                'quantity': 89.75,
            },
            {
                'gas_id': cls.env.ref('esg.esg_gas_ch4b').id,
                'esg_emission_factor_id': cls.emission_factor_computers_production.id,
                'quantity': 0.02,
            },
            {
                'gas_id': cls.env.ref('esg.esg_gas_n2o').id,
                'esg_emission_factor_id': cls.emission_factor_computers_production.id,
                'quantity': 0.01,
            },
        ])

        cls.emission_factor_delivery_transportation = cls.env['esg.emission.factor'].create({
            'name': 'Delivery Transportation',
            'source_id': cls.emission_source_downstream.id,
            'esg_uncertainty_value': 0.35,
            'compute_method': 'physically',
            'uom_id': cls.env.ref('uom.product_uom_km').id,
            'esg_emissions_value': 0.1,
        })

        cls.emission_factor_electricity_consumption = cls.env['esg.emission.factor'].create({
            'name': 'Electricity Consumption',
            'source_id': cls.emission_source_indirect.id,
            'esg_uncertainty_value': 0.25,
            'compute_method': 'monetary',
            'currency_id': cls.env.ref('base.EUR').id,
            'esg_emissions_value': 0.01,
        })

        cls.emission_factor_foreign_electricity_consumption = cls.env['esg.emission.factor'].create({
            'name': 'Foreign Electricity Consumption',
            'source_id': cls.emission_source_indirect.id,
            'esg_uncertainty_value': 0.45,
            'compute_method': 'monetary',
            'currency_id': cls.env.ref('base.USD').id,
            'esg_emissions_value': 0.05,
        })

        cls.emission_factor_phones_production = cls.env['esg.emission.factor'].create({
            'name': 'Phones Production',
            'source_id': cls.emission_source_upstream.id,
            'esg_uncertainty_value': 0.25,
            'compute_method': 'physically',
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'esg_emissions_value': 75.0,
        })
