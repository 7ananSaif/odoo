# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_ke = self.env['res.company'].create({
            'name': 'KE Co',
            'country_id': self.env.ref('base.ke').id,
        })
        self.employee_ke = self.env['hr.employee'].create({
            'name': 'KE Employee',
            'company_id': self.company_ke.id,
        })

    def test_ke_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_ke)

        template = Version.create({
            'name': 'KE Template',
            'l10n_ke_pension_contribution': 5000.0,
            'l10n_ke_food_allowance': 3000.0,
            'l10n_ke_airtime_allowance': 1500.0,
            'l10n_ke_pension_allowance': 2000.0,
            'l10n_ke_voluntary_medical_insurance': 4000.0,
            'l10n_ke_life_insurance': 2500.0,
            'l10n_ke_is_li_managed_by_employee': True,
            'l10n_ke_education': 10000.0,
            'l10n_ke_is_secondary': False,
        })

        contract = self.employee_ke.version_id

        self.assertEqual(contract.l10n_ke_pension_contribution, 0.0)
        self.assertEqual(contract.l10n_ke_food_allowance, 0.0)
        self.assertEqual(contract.l10n_ke_airtime_allowance, 0.0)
        self.assertEqual(contract.l10n_ke_pension_allowance, 0.0)
        self.assertEqual(contract.l10n_ke_voluntary_medical_insurance, 0.0)
        self.assertEqual(contract.l10n_ke_life_insurance, 0.0)
        self.assertFalse(contract.l10n_ke_is_li_managed_by_employee)
        self.assertEqual(contract.l10n_ke_education, 0.0)
        self.assertFalse(contract.l10n_ke_is_secondary)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_ke)\
            .with_context(active_model='hr.employee', active_id=self.employee_ke.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
