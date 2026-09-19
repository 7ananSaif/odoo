# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_lt = self.env['res.company'].create({
            'name': 'LT Co',
            'country_id': self.env.ref('base.lt').id,
        })
        self.employee_lt = self.env['hr.employee'].create({
            'name': 'LT Employee',
            'company_id': self.company_lt.id,
        })

    def test_lt_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_lt)

        template = Version.create({
            'name': 'LT Template',
            'l10n_lt_benefits_in_kind': 1500.0,
            'l10n_lt_time_limited': True,
            'l10n_lt_pension': True,
        })

        contract = self.employee_lt.version_id

        self.assertEqual(contract.l10n_lt_benefits_in_kind, 0.0)
        self.assertFalse(contract.l10n_lt_time_limited)
        self.assertFalse(contract.l10n_lt_pension)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_lt)\
            .with_context(active_model='hr.employee', active_id=self.employee_lt.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])

        self.assertEqual(contract.l10n_lt_working_capacity, '60_100')  # Verify that l10n_lt_working_capacity is not copied (not in whitelist)
