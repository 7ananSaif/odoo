# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_mx = self.env['res.company'].create({
            'name': 'MX Co',
            'country_id': self.env.ref('base.mx').id,
        })
        self.employee_mx = self.env['hr.employee'].create({
            'name': 'MX Employee',
            'company_id': self.company_mx.id,
        })

    def test_mx_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_mx)

        template = Version.create({
            'name': 'MX Template',
            'l10n_mx_holiday_bonus_rate': 15.0,
            'l10n_mx_savings_fund': 5.0,
            'l10n_mx_payment_period_vouchers': 'in_period',
            'l10n_mx_meal_voucher_amount': 100.0,
            'l10n_mx_transport_amount': 50.0,
            'l10n_mx_gasoline_amount': 25.0,
        })

        contract = self.employee_mx.version_id

        self.assertEqual(contract.l10n_mx_holiday_bonus_rate, 0.0)
        self.assertEqual(contract.l10n_mx_savings_fund, 0.0)

        wizard = self.env['hr.version.wizard']\
            .with_company(self.company_mx)\
            .with_context(active_model='hr.employee', active_id=self.employee_mx.id)\
            .create({'contract_template_id': template.id})
        wizard.action_load_template()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
