# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_eg = self.env['res.company'].create({
            'name': 'EG Co',
            'country_id': self.env.ref('base.eg').id,
        })
        self.employee_eg = self.env['hr.employee'].create({
            'name': 'EG Employee',
            'company_id': self.company_eg.id,
        })

    def test_eg_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_eg)

        template = Version.create({
            'name': 'EG Template',
            'l10n_eg_housing_allowance': 1500.0,
            'l10n_eg_transportation_allowance': 800.0,
            'l10n_eg_other_allowances': 600.0,
            'l10n_eg_number_of_days': 30,
            'l10n_eg_total_number_of_days': 365,
            'l10n_eg_social_insurance_reference': 4000.0,
            'l10n_eg_total_leave_days': 21.0,
        })

        contract = self.employee_eg.version_id

        self.assertEqual(contract.l10n_eg_housing_allowance, 0.0)
        self.assertEqual(contract.l10n_eg_transportation_allowance, 0.0)
        self.assertEqual(contract.l10n_eg_other_allowances, 0.0)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_eg)\
            .with_context(active_model='hr.employee', active_id=self.employee_eg.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
