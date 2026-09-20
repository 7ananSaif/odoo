# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_ro = self.env['res.company'].create({
            'name': 'RO Co',
            'country_id': self.env.ref('base.ro').id,
        })
        self.employee_ro = self.env['hr.employee'].create({
            'name': 'RO Employee',
            'company_id': self.company_ro.id,
        })

    def test_ro_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_ro)

        template = Version.create({
            'name': 'RO Template',
            'l10n_ro_work_type': '2',
        })

        contract = self.employee_ro.version_id

        self.assertEqual(contract.l10n_ro_work_type, '1')

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_ro)\
            .with_context(active_model='hr.employee', active_id=self.employee_ro.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
