# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_ma = self.env['res.company'].create({
            'name': 'MA Co',
            'country_id': self.env.ref('base.ma').id,
        })
        self.employee_ma = self.env['hr.employee'].create({
            'name': 'MA Employee',
            'company_id': self.company_ma.id,
        })

    def test_ma_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_ma)

        template = Version.create({
            'name': 'MA Template',
            'l10n_ma_kilometric_exemption': 1200.0,
            'l10n_ma_transport_exemption': 800.0,
            'l10n_ma_hra': 5000.0,
            'l10n_ma_da': 2000.0,
            'l10n_ma_meal_allowance': 1500.0,
            'l10n_ma_medical_allowance': 3000.0,
        })

        contract = self.employee_ma.version_id

        self.assertEqual(contract.l10n_ma_kilometric_exemption, 0.0)
        self.assertEqual(contract.l10n_ma_transport_exemption, 0.0)
        self.assertEqual(contract.l10n_ma_hra, 0.0)
        self.assertEqual(contract.l10n_ma_da, 0.0)
        self.assertEqual(contract.l10n_ma_meal_allowance, 0.0)
        self.assertEqual(contract.l10n_ma_medical_allowance, 0.0)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_ma)\
            .with_context(active_model='hr.employee', active_id=self.employee_ma.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
