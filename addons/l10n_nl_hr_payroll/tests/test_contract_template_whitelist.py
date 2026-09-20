# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_nl = self.env['res.company'].create({
            'name': 'NL Co',
            'country_id': self.env.ref('base.nl').id,
        })
        self.employee_nl = self.env['hr.employee'].create({
            'name': 'NL Employee',
            'company_id': self.company_nl.id,
        })

    def test_nl_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_nl)

        template = Version.create({
            'name': 'NL Template',
            'l10n_nl_30_percent': True,
        })

        contract = self.employee_nl.version_id

        self.assertEqual(contract.l10n_nl_30_percent, False)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_nl)\
            .with_context(active_model='hr.employee', active_id=self.employee_nl.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
