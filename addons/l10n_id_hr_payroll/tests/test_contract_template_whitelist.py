# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_id = self.env['res.company'].create({
            'name': 'ID Co',
            'country_id': self.env.ref('base.id').id,
        })
        self.employee_id = self.env['hr.employee'].create({
            'name': 'ID Employee',
            'company_id': self.company_id.id,
        })

    def test_id_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_id)

        template = Version.create({
            'name': 'ID Template',
            'l10n_id_bpjs_jkk': 2.5,
        })

        contract = self.employee_id.version_id

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_id)\
            .with_context(active_model='hr.employee', active_id=self.employee_id.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
