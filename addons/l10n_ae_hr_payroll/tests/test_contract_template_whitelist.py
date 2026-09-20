# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_ae = self.env['res.company'].create({
            'name': 'AE Co',
            'country_id': self.env.ref('base.ae').id,
        })
        self.employee_ae = self.env['hr.employee'].create({
            'name': 'AE Employee',
            'company_id': self.company_ae.id,
        })

    def test_ae_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_ae)

        template = Version.create({
            'name': 'AE Template',
            'l10n_ae_housing_allowance': 2000.0,
            'l10n_ae_transportation_allowance': 500.0,
            'l10n_ae_other_allowances': 300.0,
            'l10n_ae_is_dews_applied': True,
            'l10n_ae_number_of_leave_days': 25,
            'l10n_ae_is_computed_based_on_daily_salary': True,
            'l10n_ae_eos_daily_salary': 150.0,
        })

        contract = self.employee_ae.version_id

        self.assertEqual(contract.l10n_ae_housing_allowance, 0.0)
        self.assertEqual(contract.l10n_ae_transportation_allowance, 0.0)
        self.assertFalse(contract.l10n_ae_is_dews_applied)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_ae)\
            .with_context(active_model='hr.employee', active_id=self.employee_ae.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
