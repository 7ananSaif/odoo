# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import Form, tagged
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('post_install', '-at_install')
class TestSubscriptionPlan(TestSubscriptionCommon):

    def test_check_count_of_subscription_items_on_plan(self):

        # Create a subscription plan
        sub_monthly_plan = self.env['sale.subscription.plan'].create({
            'name': 'Monthly Plan',
            'billing_period_value': 1,
            'billing_period_unit': 'month',
            'sequence': 4,
        })

        # Create subscriptions
        sub_1, sub_2 = self.env['sale.order'].create([{
            'name': 'Test Subscription 1',
            'is_subscription': True,
            'plan_id': sub_monthly_plan.id,
            'partner_id': self.user_portal.partner_id.id,
            'order_line': [
                Command.create({
                    'product_id': self.product.id,
                    'name': "Monthly cheap",
                    'price_unit': 42,
                    'product_uom_qty': 2,
                }),
                Command.create({
                    'product_id': self.product2.id,
                    'name': "Monthly expensive",
                    'price_unit': 420,
                    'product_uom_qty': 3,
                }),
            ]
        }, {
            'name': 'Test Subscription 2',
            'is_subscription': True,
            'plan_id': sub_monthly_plan.id,
            'partner_id': self.user_portal.partner_id.id,
            'order_line': [
                Command.create({
                    'product_id': self.product2.id,
                    'name': "Monthly expensive",
                    'price_unit': 420,
                    'product_uom_qty': 3,
                }),
            ]
        }])

        # Confirm subscriptions
        sub_1.action_confirm()
        sub_2.action_confirm()

        # Verify the count of subscription items
        sub_plan_items = self.env['sale.subscription.plan'].search([('id', '=', sub_monthly_plan.id)])
        self.assertEqual(sub_plan_items.subscription_line_count, 3)

    def test_change_recurrence_plan_with_option(self):
        """
        A recurring order with a line for a recurring produce and a sale order option for a recurring product yields an
            exception when changing the recurring plan via Form, preventing the plan from being changed
        """
        order_1 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                Command.create({'product_id': self.product.id}),
                Command.create({
                    'name': "Optional products",
                    'display_type': 'line_section',
                    'is_optional': True,
                }),
                Command.create({
                    'product_id': self.product.id,
                }),
            ],
        })

        with Form(order_1) as order_form:
            order_form.plan_id = self.plan_week

        self.assertEqual(order_1.plan_id, self.plan_week)
