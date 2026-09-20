# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.product.tests.test_product_attribute_value_config import (
    TestProductAttributeValueCommon,
)
from odoo.addons.website_sale.tests.common import MockRequest, WebsiteSaleCommon


@tagged('post_install', '-at_install', 'product_attribute')
class TestWebsiteSaleRentingProductAttributeValueConfig(TestProductAttributeValueCommon, WebsiteSaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.computer.rent_ok = True

        recurrence_3_hour, recurrence_week = cls.env['sale.temporal.recurrence'].create([
            {
                'duration': 3,
                'unit': 'hour',
            },
            {
                'duration': 1,
                'unit': 'week',
            },
        ])
        cls.price_3_hours = 5.
        cls.price_1_week = 25.
        cls.env['product.pricing'].create([
            {
                'recurrence_id': recurrence_3_hour.id,
                'price': cls.price_3_hours,
                'product_template_id': cls.computer.id,
            }, {
                'recurrence_id': recurrence_week.id,
                'price': cls.price_1_week,
                'product_template_id': cls.computer.id,
            },
        ])

        cls.curr_eur = cls._enable_currency('EUR')

    def test_product_tax_included_get_combination_info(self):
        config = self.env['res.config.settings'].create({})
        config.show_line_subtotals_tax_selection = 'tax_included'
        config.execute()

        tax_percent = 15.0
        tax_15_incl = self.env['account.tax'].create({
            'name': 'VAT 5 perc Incl',
            'amount_type': 'percent',
            'amount': tax_percent,
            'price_include_override': 'tax_excluded',
        })
        self.computer.write({
            'taxes_id': [Command.set([tax_15_incl.id])],
        })
        factor = 1 + tax_percent / 100
        computer = self.computer.with_context(website_id=self.website.id)
        with MockRequest(self.env, website=self.website):
            price_3_hours = self.website.currency_id.round(self.price_3_hours * factor)
            price_1_week = self.website.currency_id.round(self.price_1_week * factor)
            combination_info = computer._get_combination_info()
            self.assertEqual(combination_info['price'], price_3_hours)
            self.assertEqual(combination_info['list_price'], price_3_hours)
            self.assertEqual(combination_info['has_discounted_price'], False)
            self.assertEqual(combination_info['current_rental_price'], price_3_hours)
            self.assertEqual(combination_info['current_rental_duration'], 3)
            self.assertEqual(str(combination_info['current_rental_unit']), 'Hours')
            self.assertEqual(
                combination_info['pricing_table'],
                [('3 Hours', f'$\xa0{price_3_hours}'), ('1 Week', f'$\xa0{price_1_week}')],
            )

    def test_product_attribute_value_config_get_combination_info(self):
        # make sure the pricelist has a 10% discount
        self.env['product.pricelist.item'].create({
            'price_discount': 10,
            'compute_price': 'formula',
            'pricelist_id': self.pricelist.id,
        })
        self.assertTrue(self.pricelist._is_available_on_website(self.website))

        discount_rate = 1 # No discount should apply on rental products (functional choice)

        self.curr_eur.rate_ids = [Command.create({'rate': 3.0})]
        currency_ratio = self.curr_eur.rate
        self.pricelist.currency_id = self.curr_eur

        computer = self.computer.with_context(website_id=self.website.id)
        with MockRequest(self.env, website=self.website, website_sale_current_pl=self.pricelist.id) as request:
            self.assertEqual(request.pricelist, self.pricelist)
            self.assertEqual(request.website.currency_id, self.pricelist.currency_id)
            price_3_hours = self.website.currency_id.round(
                self.price_3_hours * discount_rate * currency_ratio
            )
            price_1_week = self.website.currency_id.round(
                self.price_1_week * discount_rate * currency_ratio
            )
            combination_info = computer._get_combination_info()
            self.assertEqual(combination_info['price'], price_3_hours)
            self.assertEqual(combination_info['list_price'], price_3_hours)
            self.assertEqual(combination_info['has_discounted_price'], False)
            self.assertEqual(combination_info['current_rental_price'], price_3_hours)
            self.assertEqual(combination_info['current_rental_duration'], 3)
            self.assertEqual(str(combination_info['current_rental_unit']), 'Hours')

        now = self.env.cr.now()
        with MockRequest(self.env, website=self.website, website_sale_current_pl=self.pricelist.id):
            combination_info = computer.with_context(
                start_date=now, end_date=now + relativedelta(days=6)
            )._get_combination_info()
            self.assertEqual(combination_info['price'], price_3_hours)
            self.assertEqual(combination_info['list_price'], price_3_hours)
            self.assertEqual(combination_info['has_discounted_price'], False)
            self.assertEqual(combination_info['current_rental_price'], price_1_week)
            self.assertEqual(combination_info['current_rental_duration'], 1)
            self.assertEqual(str(combination_info['current_rental_unit']), 'Week')
