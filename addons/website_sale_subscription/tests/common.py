# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command

from odoo.addons.sale_subscription.tests.common_sale_subscription import SaleSubscriptionCommon
from odoo.addons.website_sale.tests.common import WebsiteSaleCommon


class WebsiteSaleSubscriptionCommon(SaleSubscriptionCommon, WebsiteSaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.sub_product, cls.sub_product_2, cls.sub_product_3 = cls.env['product.template'].create([
            {
                'name': 'Streaming SUB Weekly',
                'list_price': 0,
                'recurring_invoice': True,
            },
            {
                'name': 'Streaming SUB Monthly',
                'list_price': 0,
                'recurring_invoice': True,
            },
            {
                'name': 'Streaming SUB Yearly',
                'list_price': 0,
                'recurring_invoice': True,
            }
        ])

        cls.env['product.pricelist.item'].create([
            {
                'plan_id': cls.plan_week.id,
                'fixed_price': 5.0,
                'product_tmpl_id': cls.sub_product.id,
            },
            {
                'plan_id': cls.plan_month.id,
                'fixed_price': 25.0,
                'product_tmpl_id': cls.sub_product_2.id,
            }
        ])

        cls.pricelist_111 = cls.env['product.pricelist'].create({
            'name': 'Pricelist111',
            'selectable': True,
            'company_id': False,
            'item_ids': [
                Command.create({
                    'plan_id': cls.plan_year.id,
                    'fixed_price': 111.0,
                    'product_tmpl_id': cls.sub_product_3.id,
                })
            ]
        })
        cls.pricelist_222 = cls.env['product.pricelist'].create({
            'name': 'Pricelist222',
            'selectable': True,
            'company_id': False,
            'item_ids': [
                Command.create({
                    'plan_id': cls.plan_year.id,
                    'fixed_price': 222.0,
                    'product_tmpl_id': cls.sub_product_3.id,
                })
            ]
        })

        # create product one time subscription
        cls.one_time_sub_product = cls.env['product.template'].create({
            'name': 'One time subscription',
            'list_price': 30.0,
            'recurring_invoice': True,
            'allow_one_time_sale': True,
            'type': 'consu',
        })
        cls.env['product.pricelist.item'].create([
            {
                'plan_id': cls.plan_month.id,
                'fixed_price': 10.0,
                'product_tmpl_id': cls.one_time_sub_product.id,
            }
        ])

        # create product with variants
        cls.product_attribute = cls.env['product.attribute'].create({
            'name': 'Color',
            'value_ids': [
                Command.create({
                    'name': 'Black',
                }),
                Command.create({
                    'name': 'White',
                })
            ]
        })

        cls.sub_with_variants = cls.env['product.template'].create({
            'recurring_invoice': True,
            'type': 'service',
            'name': 'Variant Products',
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': cls.product_attribute.id,
                    'value_ids': [Command.set(cls.product_attribute.value_ids.ids)]
                })
            ]
        })

        cls.env['product.pricelist.item'].create([
            {
                'plan_id': cls.plan_week.id,
                'fixed_price': 10,
                'product_tmpl_id': cls.sub_with_variants.id,
                'product_id': cls.sub_with_variants.product_variant_ids[0].id,
            },
            {
                'plan_id': cls.plan_month.id,
                'fixed_price': 25,
                'product_tmpl_id': cls.sub_with_variants.id,
                'product_id': cls.sub_with_variants.product_variant_ids[1].id,
            }
        ])
