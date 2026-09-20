# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_us = self.env['res.company'].create({
            'name': 'US Co',
            'country_id': self.env.ref('base.us').id,
        })
        self.worker_comp = self.env['l10n.us.worker.compensation'].create({'name': 'WC A'})
        self.employee_us = self.env['hr.employee'].create({
            'name': 'US Employee',
            'company_id': self.company_us.id,
        })

    def test_us_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_us)

        template = Version.create({
            'name': 'US Template',
            'l10n_us_pre_retirement_amount': 5.0,
            'l10n_us_pre_retirement_type': 'percent',
            'l10n_us_pre_retirement_matching_amount': 1.0,
            'l10n_us_pre_retirement_matching_type': 'fixed',
            'l10n_us_pre_retirement_matching_yearly_cap': 1000.0,
            'l10n_us_post_roth_401k_amount': 2.0,
            'l10n_us_post_roth_401k_type': 'fixed',
            'l10n_us_health_benefits_medical': 150.0,
            'l10n_us_health_benefits_dental': 25.0,
            'l10n_us_health_benefits_vision': 10.0,
            'l10n_us_health_benefits_fsa': 100.0,
            'l10n_us_health_benefits_fsadc': 200.0,
            'l10n_us_health_benefits_hsa': 300.0,
            'l10n_us_commuter_benefits': 75.0,
            'l10n_us_worker_compensation_id': self.worker_comp.id,
            'l10n_us_w4_step_4a': 99.0,
        })

        contract = self.employee_us.version_id

        self.assertEqual(contract.l10n_us_pre_retirement_amount, 0.0)
        self.assertEqual(contract.l10n_us_health_benefits_medical, 0.0)
        self.assertFalse(contract.l10n_us_worker_compensation_id)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_us)\
            .with_context(active_model='hr.employee', active_id=self.employee_us.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])

        self.assertEqual(contract.l10n_us_w4_step_4a, 0.0)  # This field is not in the whitelist so it shouldn't be copied from the template
