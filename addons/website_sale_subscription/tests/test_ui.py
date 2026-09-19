# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import HttpCase, tagged

from odoo.addons.website_sale_subscription.tests.common import WebsiteSaleSubscriptionCommon


@tagged('-at_install', 'post_install')
class TestWebsiteSaleSubscriptionUi(HttpCase, WebsiteSaleSubscriptionCommon):

    def test_website_sale_subscription_ui(self):
        self.start_tour("/odoo", 'shop_buy_subscription_product', login='admin')

    def test_website_sale_subscription_product_variants(self):
        product_attribute = self.env['product.attribute'].create({
            'name': 'periods',
            'value_ids': [
                Command.create({'name': 'Monthly'}),
                Command.create({'name': '2 Months'}),
                Command.create({'name': 'Yearly'}),
            ]
        })

        reccuring_product = self.env['product.template'].create({
            'recurring_invoice': True,
            'type': 'service',
            'name': 'Reccuring product',
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': product_attribute.id,
                    'value_ids': [Command.set(product_attribute.value_ids.ids)],
                }),
            ]
        })

        self.env['product.pricelist.item'].create([
            {
                'plan_id': self.plan_month.id,
                'fixed_price': 90,
                'product_tmpl_id': reccuring_product.id,
                'product_id': reccuring_product.product_variant_ids[-3].id,
            }, {
                'plan_id': self.plan_2_month.id,
                'fixed_price': 160,
                'product_tmpl_id': reccuring_product.id,
                'product_id': reccuring_product.product_variant_ids[-2].id,
            }, {
                'plan_id': self.plan_year.id,
                'fixed_price': 1000,
                'product_tmpl_id': reccuring_product.id,
                'product_id': reccuring_product.product_variant_ids[-1].id,
            }
        ])

        self.start_tour(reccuring_product.website_url, 'sale_subscription_product_variants', login='admin')

    def test_website_sale_subscription_product_variant_add_to_cart(self):
        product_attribute = self.env['product.attribute'].create({
            'name': 'Color',
            'value_ids': [
                Command.create({'name': 'Black'}),
                Command.create({'name': 'White'}),
            ]
        })
        test_product = self.env['product.template'].create({
            'name': 'Product with Color',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.uom_unit.id,
            'website_published': True,
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': product_attribute.id,
                    'value_ids': [
                        Command.set(product_attribute.value_ids.ids),
                    ],
                }),
            ],
            'subscription_rule_ids': [
                Command.create({'plan_id': self.plan_month.id, 'fixed_price': 1}),
                Command.create({'plan_id': self.plan_year.id, 'fixed_price': 100}),
            ],
        })

        self.start_tour(test_product.website_url, 'sale_subscription_add_to_cart', login='admin')
