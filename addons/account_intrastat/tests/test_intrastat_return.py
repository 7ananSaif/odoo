from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


def patched_generate_all_returns(account_return_type, country_code, main_company, tax_unit=None):
    TestIntrastatReturn.return_type._try_create_returns_for_fiscal_year(main_company, tax_unit)


@tagged('post_install', '-at_install')
class TestIntrastatReturn(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        country = cls.env['res.country'].create({
            'name': 'Squamuglia',
            'code': 'SQ',
        })
        intrastat_country_group = cls.env.ref('account.intrastat')
        intrastat_country_group.country_ids |= country
        cls.company_data['company'].country_id = country
        cls.company_data['company'].currency_id = cls.env.ref('base.EUR').id
        cls.company_data['currency'] = cls.env.ref('base.EUR')

        cls.return_type = cls.env['account.return.type'].create({
            'name': 'Test Intrastat Return Type',
            'report_id': cls.env.ref('account_intrastat.intrastat_report').id,
        })

        cls.startClassPatcher(freeze_time('2022-01-15'))

        with cls._patch_returns_generation():
            cls.env.company.account_opening_date = '2022-01-01'

    @classmethod
    def _patch_returns_generation(cls):
        return patch.object(cls.registry['account.return.type'], '_generate_all_returns', patched_generate_all_returns)

    def assert_return_contains_checks(self, account_return, expected_check_codes):
        checks_by_code = {check.code: check for check in account_return.check_ids}
        missing_checks = [code for code in expected_check_codes if code not in checks_by_code]

        if missing_checks:
            self.fail(f"Missing checks in return: {', '.join(missing_checks)}")

    def test_intrastat_checks(self):
        """ Test that all the checks are present in the first return """

        january_return = self.env['account.return'].search([
            ('type_id', '=', self.return_type.id),
            ('company_id', '=', self.env.company.id),
            ('date_from', '=', '2022-01-01'),
            ('date_to', '=', '2022-01-31'),
        ])

        self.assertEqual(len(january_return), 1, "There should be one return for January 2022")

        january_return.refresh_checks()

        checks = january_return.check_ids

        self.assert_return_contains_checks(
            january_return,
            [
                'check_intrastat_commodity_code',
                'check_intrastat_threshold',
                'check_intrastat_only_b2b_customer',
                'check_intrastat_only_goods',
                'check_intrastat_only_intra_eu',
                'check_intrastat_uom',
                'check_intrastat_vat_exclusive',
            ],
        )

        only_b2b_customer_check = checks.filtered(lambda c: c.code == 'check_intrastat_only_b2b_customer')
        self.assertEqual(
            only_b2b_customer_check.result,
            'reviewed',
            "The check for only B2B customers should pass as there are no private individuals in the January return",
        )

        # make the check fail by adding a private individual
        private_individuals = self.env['res.partner'].create([
            {
                'name': 'Private Individual with VAT',
                'is_company': False,
                'country_id': self.env.ref('base.us').id,
                'vat': 'US123456789',
            },
            {
                'name': 'Private Individual without VAT',
                'is_company': False,
                'country_id': self.env.ref('base.us').id,
                'vat': '/',
            }
        ])

        invoices = self.env['account.move'].create([
            {
                'move_type': 'out_invoice',
                'partner_id': private_individuals[0].id,
                'date': '2022-01-15',
                'currency_id': self.env.company.currency_id.id,
                'company_id': self.env.company.id,
                'invoice_line_ids': [Command.create({
                    'name': 'Test Product',
                    'quantity': 1.0,
                    'price_unit': 100.0,
                    'product_uom_id': self.env.ref('uom.product_uom_unit').id,
                })],
            },
            {
                'move_type': 'out_invoice',
                'partner_id': private_individuals[1].id,
                'date': '2022-01-15',
                'currency_id': self.env.company.currency_id.id,
                'company_id': self.env.company.id,
                'invoice_line_ids': [Command.create({
                    'name': 'Test Product',
                    'quantity': 1.0,
                    'price_unit': 100.0,
                    'product_uom_id': self.env.ref('uom.product_uom_unit').id,
                })],
            },
        ])
        invoices.action_post()

        january_return.refresh_checks()

        only_b2b_customer_check = self.env['account.return.check'].browse(only_b2b_customer_check.id)
        self.assertEqual(
            only_b2b_customer_check.result,
            'anomaly',
            "The check for only B2B customers should fail as there is now a private individual in the January return",
        )

        self.assertEqual(only_b2b_customer_check.records_count, 1, "Only one partner must fail, as one has a VAT but the other not")

        invoices[1].button_draft()
        january_return.refresh_checks()
        self.assertEqual(
            only_b2b_customer_check.result,
            'reviewed',
            "The check should now succeed as we removed the failing partner move",
        )
