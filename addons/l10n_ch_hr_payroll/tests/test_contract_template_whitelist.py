# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_ch = self.env['res.company'].create({
            'name': 'CH Co',
            'country_id': self.env.ref('base.ch').id,
        })
        self.employee_ch = self.env['hr.employee'].create({
            'name': 'CH Employee',
            'company_id': self.company_ch.id,
        })

    def test_ch_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_ch)

        template = Version.create({
            'name': 'CH Template',
            'l10n_ch_contractual_13th_month_rate': 8.33,
            'l10n_ch_lesson_wage': 50.0,
            'l10n_ch_lpp_not_insured': False,
            'l10n_ch_monthly_effective_days': 21.5,
            'l10n_ch_other_employers': False,
            'l10n_ch_other_employers_occupation_rate': 0.0,
            'l10n_ch_thirteen_month': True,
            'l10n_ch_yearly_holidays': 25,
            'l10n_ch_yearly_paid_public_holidays': 10,
            'l10n_ch_accident_insurance_line_id': False,
            'l10n_ch_additional_accident_insurance_line_ids': [],
            'l10n_ch_avs_status': False,
            'l10n_ch_compensation_fund_id': False,
            'l10n_ch_is_model': False,
            'l10n_ch_is_predefined_category': False,
            'l10n_ch_job_type': False,
            'l10n_ch_location_unit_id': False,
            'l10n_ch_lpp_insurance_id': False,
            'l10n_ch_sickness_insurance_line_ids': [],
            'l10n_ch_social_insurance_id': False,
            'l10n_ch_total_occupation_rate': 100.0,
        })

        contract = self.employee_ch.version_id

        self.assertAlmostEqual(contract.l10n_ch_contractual_13th_month_rate, 8.33, places=2)
        self.assertEqual(contract.l10n_ch_lesson_wage, 0.0)
        self.assertEqual(contract.l10n_ch_monthly_effective_days, 20.0)  # Default value

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_ch)\
            .with_context(active_model='hr.employee', active_id=self.employee_ch.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
