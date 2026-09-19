# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_au = self.env['res.company'].create({
            'name': 'AU Co',
            'country_id': self.env.ref('base.au').id,
        })
        self.employee_au = self.env['hr.employee'].create({
            'name': 'AU Employee',
            'company_id': self.company_au.id,
        })

    def test_au_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_au)

        template = Version.create({
            'name': 'AU Template',
            'l10n_au_casual_loading': 0.25,
            'l10n_au_cessation_type_code': 'V',
            'l10n_au_eligible_for_leave_loading': True,
            'l10n_au_extra_compulsory_super': 0.02,
            'l10n_au_extra_negotiated_super': 0.015,
            'l10n_au_leave_loading': 'regular',
            'l10n_au_leave_loading_rate': 17.5,
            'l10n_au_pay_day': '4',
            'l10n_au_performances_per_week': 5,
            'l10n_au_salary_sacrifice_other': 100.0,
            'l10n_au_salary_sacrifice_superannuation': 200.0,
            'l10n_au_workplace_giving': 50.0,
            'l10n_au_workplace_giving_employer': 25.0,
            'l10n_au_yearly_wage': 75000.0,
        })

        contract = self.employee_au.version_id

        self.assertEqual(contract.l10n_au_casual_loading, 0.0)
        self.assertFalse(contract.l10n_au_eligible_for_leave_loading)
        self.assertEqual(contract.l10n_au_extra_compulsory_super, 0.0)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_au)\
            .with_context(active_model='hr.employee', active_id=self.employee_au.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
