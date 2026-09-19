# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_sa = self.env['res.company'].create({
            'name': 'SA Co',
            'country_id': self.env.ref('base.sa').id,
        })
        self.employee_sa = self.env['hr.employee'].create({
            'name': 'SA Employee',
            'company_id': self.company_sa.id,
        })

    def test_sa_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_sa)

        template = Version.create({
            'name': 'SA Template',
            'l10n_sa_housing_allowance': 1500.0,
            'l10n_sa_transportation_allowance': 500.0,
            'l10n_sa_other_allowances': 300.0,
            'l10n_sa_number_of_days': 30,
            'l10n_sa_wps_description': 'Monthly Salary',
        })

        contract = self.employee_sa.version_id

        self.assertEqual(contract.l10n_sa_housing_allowance, 0.0)
        self.assertEqual(contract.l10n_sa_transportation_allowance, 0.0)
        self.assertEqual(contract.l10n_sa_other_allowances, 0.0)
        self.assertEqual(contract.l10n_sa_number_of_days, 21)
        self.assertFalse(contract.l10n_sa_wps_description)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_sa)\
            .with_context(active_model='hr.employee', active_id=self.employee_sa.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
