# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_be = self.env['res.company'].create({
            'name': 'BE Co',
            'country_id': self.env.ref('base.be').id,
        })
        self.employee_be = self.env['hr.employee'].create({
            'name': 'BE Employee',
            'company_id': self.company_be.id,
            'certificate': 'bachelor',  # Required for rd_percentage field validation
        })

    def test_be_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_be)

        template = Version.create({
            'name': 'BE Template',
            'wage': 4000.0,
            'wage_type': 'monthly',
            'hourly_wage': 25.0,
            'commission_on_target': 5000.0,
            'representation_fees': 200.0,
            'ip': True,
            'ip_wage_rate': 25.0,
            'mobile': 50.0,
            'internet': 30.0,
            'has_laptop': True,
            'meal_voucher_amount': 8.0,
            'eco_checks': 250.0,
            'l10n_be_canteen_cost': 5.0,
            'l10n_be_group_insurance_rate': 2.5,
            'l10n_be_mobility_budget': True,
            'l10n_be_mobility_budget_amount': 500.0,
            'l10n_be_mobility_budget_amount_monthly': 50.0,
            'has_hospital_insurance': True,
            'insurance_amount': 100.0,
            'insured_relative_spouse': True,
            'insured_relative_adults': 1,
            'insured_relative_children': 2,
            'l10n_be_has_ambulatory_insurance': True,
            'l10n_be_ambulatory_insurance_amount': 75.0,
            'l10n_be_ambulatory_insured_spouse': True,
            'l10n_be_ambulatory_insured_adults': 1,
            'l10n_be_ambulatory_insured_children': 2,
            'transport_mode_car': True,
            'fuel_card': 150.0,
            'car_atn': 200.0,
            'transport_mode_train': False,
            'transport_mode_public': False,
            'transport_mode_private_car': False,
            'transport_mode_bike': True,
            'distance_home_work': 25,
            'distance_home_work_unit': 'kilometers',
            'private_car_reimbursed_amount': 0.3,
            'train_transport_employee_amount': 100.0,
            'train_transport_reimbursed_amount': 80.0,
            'public_transport_employee_amount': 50.0,
            'public_transport_reimbursed_amount': 40.0,
            'fiscal_voluntarism': 100.0,
            'no_onss': False,
            'no_withholding_taxes': False,
            'rd_percentage': 5.0,
            'l10n_be_impulsion_plan': False,
            'l10n_be_onss_restructuring': False,
            'l10n_be_is_below_scale': False,
            'employee_age': 30,
        })

        contract = self.employee_be.version_id

        self.assertEqual(contract.commission_on_target, 0.0)
        self.assertEqual(contract.representation_fees, 150.0)  # Default value
        self.assertFalse(contract.ip)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_be)\
            .with_context(active_model='hr.employee', active_id=self.employee_be.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
