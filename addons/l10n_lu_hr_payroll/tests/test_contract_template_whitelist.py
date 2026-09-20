# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_lu = self.env['res.company'].create({
            'name': 'LU Co',
            'country_id': self.env.ref('base.lu').id,
        })
        self.employee_lu = self.env['hr.employee'].create({
            'name': 'LU Employee',
            'company_id': self.company_lu.id,
        })

    def test_lu_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_lu)

        template = Version.create({
            'name': 'LU Template',
            'l10n_lu_meal_voucher_amount': 250.0,
            'l10n_lu_meal_voucher_employee_computation': 'consider_as_bik',
            'l10n_lu_bik_vehicle': 5000.0,
            'l10n_lu_bik_vehicle_vat_included': False,
            'l10n_lu_bik_other_benefits': 1500.0,
            'l10n_lu_alw_vehicle': 2000.0,
            'l10n_lu_tax_classification': '2',  # Field not in whitelist
        })

        contract = self.employee_lu.version_id

        self.assertEqual(contract.l10n_lu_meal_voucher_amount, 0.0)
        self.assertEqual(contract.l10n_lu_meal_voucher_employee_computation, 'removed_from_net')
        self.assertEqual(contract.l10n_lu_bik_vehicle, 0.0)
        self.assertTrue(contract.l10n_lu_bik_vehicle_vat_included)  # Default is True

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_lu)\
            .with_context(active_model='hr.employee', active_id=self.employee_lu.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])

        self.assertEqual(contract.l10n_lu_tax_classification, '1')  # This field is not in the whitelist so it shouldn't be copied from the template
