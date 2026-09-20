# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_in = self.env['res.company'].create({
            'name': 'IN Co',
            'country_id': self.env.ref('base.in').id,
        })
        self.employee_in = self.env['hr.employee'].create({
            'name': 'IN Employee',
            'company_id': self.company_in.id,
        })

    def test_in_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_in)

        template = Version.create({
            'name': 'IN Template',
            'l10n_in_tds': 2000.0,
            'l10n_in_medical_insurance': 5000.0,
            'l10n_in_provident_fund': True,
            'l10n_in_gratuity': 15000.0,
        })

        contract = self.employee_in.version_id

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_in)\
            .with_context(active_model='hr.employee', active_id=self.employee_in.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
