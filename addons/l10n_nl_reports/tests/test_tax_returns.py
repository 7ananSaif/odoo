from unittest.mock import patch
from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.tools import float_compare
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


def patched_generate_all_returns(account_return_type, country_code, main_company, tax_unit=None):
    TestTaxReturn.basic_return_type._try_create_returns_for_fiscal_year(main_company, tax_unit)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestTaxReturn(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_country('nl')
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].write({
            'vat': 'NL123456782B90',
            'phone': '123456789',
            'email': 'test@gmail.com',
        })

        cls.partner_a.country_id = cls.env.ref('base.nl')
        cls.invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': '2024-01-01',
            'partner_id': cls.partner_a.id,
            'invoice_line_ids': [Command.create({
                'name': f"{i}",
                'product_id': cls.product_a.id,
                'price_unit': 0.1,
            }) for i in range(100)],
        })
        cls.invoice.action_post()

        cls.basic_return_type = cls.env.ref('l10n_nl_reports.nl_tax_return_type')
        cls.startClassPatcher(freeze_time('2024-01-16'))

        with cls._patch_returns_generation():
            cls.env.company.account_opening_date = '2024-02-01'  # This will make the first return to be generated in January

    @classmethod
    def _patch_returns_generation(cls):
        return patch.object(cls.registry['account.return.type'], '_generate_all_returns', patched_generate_all_returns)

    def test_vat_closing_moves_with_difference_from_rounding_taxes(self):
        """ Checks a closing entry with rounding difference """
        first_return = self.env['account.return'].search([
            ('type_id', '=', self.basic_return_type.id),
            ('company_id', '=', self.env.company.id),
        ], order='date_from', limit=1)
        with self.allow_pdf_render():
            first_return.action_validate()
        self.assertTrue(first_return.closing_move_ids)

        move_line_with_difference_from_rounding_taxes = next(l for l in first_return.closing_move_ids.invoice_line_ids if l.name == 'Difference from rounding taxes')
        self.assertFalse(float_compare(abs(move_line_with_difference_from_rounding_taxes.balance), self.invoice.amount_tax, 2) == 0)
