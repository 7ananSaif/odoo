# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.tests.common import MockRequest

from .common import WebsiteSaleSubscriptionCommon


@tagged('post_install', '-at_install')
class TestWebsiteSaleSubscription(WebsiteSaleSubscriptionCommon):

    def test_cart_update_so_reccurence(self):
        self.env['product.pricelist'].sudo().search([('active', '=', True)]).action_archive()
        self.env['product.pricelist.item'].search([('plan_id', '!=', False)]).pricelist_id = False
        # Product not recurring
        product = self.env['product.template'].with_context(website_id=self.website.id).create({
            'name': 'Non-recurring Product',
            'list_price': 15,
            'type': 'service',
        })

        # Mocking to check if error raised on Website when adding
        # 2 subscription product with different recurrence
        with MockRequest(self.env, website=self.website) as request:
            so = request.website._create_cart()
            self.assertFalse(so.plan_id)
            so._cart_add(product_id=product.product_variant_ids.id, quantity=1)
            self.assertFalse(so.plan_id)
            so._cart_add(product_id=self.sub_product.product_variant_ids.id, quantity=1)
            self.assertEqual(so.plan_id, self.plan_week)
            with self.assertRaises(UserError, msg="You can't add a subscription product to a sale order with another recurrence."):
                # Must go through controller since _is_add_to_cart_allowed is checked there
                Cart().add_to_cart(
                    product_template_id=self.sub_product_2.id,
                    product_id=self.sub_product_2.product_variant_id.id,
                    quantity=1.0,
                )
            so._cart_update_line_quantity(
                line_id=so.order_line.filtered(
                    lambda sol: sol.product_id == self.sub_product.product_variant_id
                ).id,
                quantity=0,
            )
            self.assertFalse(so.plan_id)
            so._cart_add(product_id=self.sub_product_2.product_variant_ids.id, quantity=1)
            self.assertEqual(so.plan_id, self.plan_month)
            so._cart_update_line_quantity(
                line_id=so.order_line.filtered(
                    lambda sol: sol.product_id == self.sub_product_2.product_variant_id
                ).id,
                quantity=0,
            )
            self.assertFalse(so.plan_id)

    def test_combination_info_product(self):
        self.sub_product = self.sub_product.with_context(website_id=self.website.id)

        with MockRequest(self.env, website=self.website) as request:
            self.assertEqual(request.pricelist, self.pricelist)
            combination_info = self.sub_product._get_combination_info()
            self.assertEqual(combination_info['price'], 5)
            self.assertTrue(combination_info['is_subscription'])
            self.assertEqual(combination_info['subscription_default_pricing_plan_id'], self.plan_week.id)
            self.assertEqual(combination_info['subscription_default_pricing_price'], 'Weekly: $ 5.00')

    def test_combination_info_variant_products(self):
        template = self.sub_with_variants.with_context(website_id=self.website.id)
        with MockRequest(self.env, website=self.website) as request:
            self.assertEqual(request.pricelist, self.pricelist)
            combination_info = template.product_variant_ids[0]._get_combination_info_variant()
        self.assertEqual(combination_info['price'], 10)
        self.assertTrue(combination_info['is_subscription'])
        self.assertEqual(combination_info['subscription_default_pricing_plan_id'], self.plan_week.id)
        self.assertEqual(combination_info['subscription_default_pricing_price'], 'Weekly: $ 10.00')

        with MockRequest(self.env, website=self.website) as request:
            self.assertEqual(request.pricelist, self.pricelist)
            combination_info_variant_2 = template.product_variant_ids[-1]._get_combination_info_variant()
        self.assertEqual(combination_info_variant_2['price'], 25)
        self.assertTrue(combination_info_variant_2['is_subscription'])
        self.assertEqual(combination_info_variant_2['subscription_default_pricing_plan_id'], self.plan_month.id)
        self.assertEqual(combination_info_variant_2['subscription_default_pricing_price'], 'Monthly: $ 25.00')

    def test_combination_info_multi_pricelist(self):
        product = self.sub_product_3.with_context(website_id=self.website.id)

        with MockRequest(self.env, website=self.website, website_sale_current_pl=self.pricelist_111.id):
            combination_info = product._get_combination_info(only_template=True)
            self.assertEqual(combination_info['price'], 111)

        with MockRequest(self.env, website=self.website, website_sale_current_pl=self.pricelist_222.id):
            combination_info = product._get_combination_info(only_template=True)
            self.assertEqual(combination_info['price'], 222)

    def test_cart_add_one_time_and_plan_product(self):
        one_time_product = self.one_time_sub_product

        # Case 1: Add to cart without a plan (one-time purchase)
        with MockRequest(self.env, website=self.website) as request:
            so = request.website._create_cart()
            self.assertFalse(so.plan_id)
            so._cart_add(product_id=one_time_product.product_variant_ids.id, quantity=1)

            # Check product in order line
            so.plan_id = False

            self.assertTrue(so.order_line)
            self.assertEqual(so.order_line.product_id, one_time_product.product_variant_ids)
            self.assertEqual(so.order_line.price_unit, one_time_product.list_price)

        # Case 2: Add to cart with a plan selected
        with MockRequest(self.env, website=self.website) as request:
            so = request.website._create_cart()
            so._cart_add(product_id=one_time_product.product_variant_ids.id, quantity=1)

            # Check product and price with plan applied

            self.assertTrue(so.order_line)
            self.assertEqual(so.order_line.product_id, one_time_product.product_variant_ids)
            self.assertEqual(so.plan_id, self.plan_month)

    def test_subscription_plan_discount_percentage(self):
        """Test discount percentage calculation"""
        # Case 1: Service subscription product
        product = self.env['product.template'].create({
            'name': 'Discounted Subscription', 'recurring_invoice': True, 'type': 'service',
        })
        self.env['product.pricelist.item'].create([
            {'plan_id': self.plan_week.id, 'fixed_price': 100.0, 'product_tmpl_id': product.id},
            {'plan_id': self.plan_month.id, 'fixed_price': 180.0, 'product_tmpl_id': product.id},
            {'plan_id': self.plan_year.id, 'fixed_price': 1000.0, 'product_tmpl_id': product.id},
        ])

        with MockRequest(self.env, website=self.website):
            pricings = product._get_combination_info().get('pricings', [])

        weekly = next(p for p in pricings if p['plan_id'] == self.plan_week.id)
        monthly = next(p for p in pricings if p['plan_id'] == self.plan_month.id)
        yearly = next(p for p in pricings if p['plan_id'] == self.plan_year.id)
        self.assertEqual(weekly['discounted_price'], 0.0)  # Weekly plan no discount
        self.assertEqual(monthly['discounted_price'], 58)  # Monthly 10% discount
        self.assertEqual(yearly['discounted_price'], 80.0)  # Yearly 80% discount

        # Case 2: Consumable subscription product
        product.type = 'consu'
        with MockRequest(self.env, website=self.website):
            pricings = product._get_combination_info().get('pricings', [])

        weekly = next(p for p in pricings if p['plan_id'] == self.plan_week.id)
        monthly = next(p for p in pricings if p['plan_id'] == self.plan_month.id)
        yearly = next(p for p in pricings if p['plan_id'] == self.plan_year.id)
        self.assertEqual(weekly['discounted_price'], 90.0)  # Weekly 90% cheaper than yearly
        self.assertEqual(monthly['discounted_price'], 82.0)  # Monthly 82% cheaper than yearly
        self.assertEqual(yearly['discounted_price'], 0.0)  # Yearly is base price

        # Case 3: One-time purchase + subscription
        product.list_price = 1500  # One-time price
        product.allow_one_time_sale = True
        with MockRequest(self.env, website=self.website):
            pricings = product._get_combination_info().get('pricings', [])

        weekly = next(p for p in pricings if p['plan_id'] == self.plan_week.id)
        monthly = next(p for p in pricings if p['plan_id'] == self.plan_month.id)
        yearly = next(p for p in pricings if p['plan_id'] == self.plan_year.id)
        self.assertEqual(weekly['discounted_price'], 93)  # Weekly 93% discount vs one-time
        self.assertEqual(monthly['discounted_price'], 88)  # Monthly 88% discount vs one-time
        self.assertEqual(yearly['discounted_price'], 33)  # Yearly 33% discount vs one-time

    def test_cart_add_one_time_then_recurring_not_allowed(self):
        """
        Test that a cart cannot mix one-time and subscription products.
        Allows adding one-time, blocks adding subscription after it,
        but works once the one-time product is removed.
        """
        one_time_product = self.one_time_sub_product
        with MockRequest(self.env, website=self.website) as request:
            so = request.website._create_cart()

            # Add one-time product
            so._cart_add(product_id=one_time_product.product_variant_ids.id, quantity=1)
            so.plan_id = False

            with self.assertRaises(UserError, msg="You can't add a subscription product to a sale order with a one-time product."):
                Cart().add_to_cart(
                    product_template_id=self.sub_product.id,
                    product_id=self.sub_product.product_variant_id.id,
                    quantity=1.0,
                )

            so._cart_update_line_quantity(
                line_id=so.order_line.filtered(
                    lambda sol: sol.product_id == one_time_product.product_variant_id
                ).id,
                quantity=0,
            )
            self.assertFalse(so.plan_id)

            so._cart_add(product_id=self.sub_product.product_variant_ids.id, quantity=1)
            self.assertEqual(so.plan_id, self.plan_week)

    def test_subscription_requires_partner_country(self):
        """ Test that a subscription product in the cart requires the partner to set its country."""
        self.partner.country_id = False
        with MockRequest(self.env, website=self.website) as request:
            request.website._create_cart()
            Cart().add_to_cart(
                product_template_id=self.sub_product.id,
                product_id=self.sub_product.product_variant_id.id,
                quantity=1.0,
            )
            mandatory_fields = CustomerPortal()._get_mandatory_delivery_address_fields(
                self.partner.country_id
            )
            self.assertTrue('country_id' in mandatory_fields)
