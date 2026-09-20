# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_sk = self.env['res.company'].create({
            'name': 'SK Co',
            'country_id': self.env.ref('base.sk').id,
        })
        self.employee_sk = self.env['hr.employee'].create({
            'name': 'SK Employee',
            'company_id': self.company_sk.id,
        })

    def test_sk_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_sk)

        template = Version.create({
            'name': 'SK Template',
            'l10n_sk_meal_voucher_employee': 50.0,
            'l10n_sk_meal_voucher_employer': 100.0,
        })

        contract = self.employee_sk.version_id

        self.assertEqual(contract.l10n_sk_meal_voucher_employee, 0.0)
        self.assertEqual(contract.l10n_sk_meal_voucher_employer, 0.0)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_sk)\
            .with_context(active_model='hr.employee', active_id=self.employee_sk.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
