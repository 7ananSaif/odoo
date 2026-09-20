# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.sale_subscription_partnership.tests.common import SubscriptionsPartnershipCommon


class TestSubscriptionsPartnership(SubscriptionsPartnershipCommon):

    def test_assign_plan_via_sale_order(self):
        plan, plan_2 = self.env['commission.plan'].create([{
            'name': 'Gold Plan',
            'product_id': self.env.ref('partner_commission.product_commission').id,
        }, {
            'name': 'Silver Plan',
            'product_id': self.env.ref('partner_commission.product_commission').id,
        }])
        self.partner_grade.default_commission_plan_id = plan.id
        self.sale_order_partnership.action_confirm()
        self.assertEqual(
            self.partner.commission_plan_id, plan,
            "Selling the partnership should assign the commission plan to the partner",
        )
        self.partner.commission_plan_id = plan_2.id
        self.sale_order_partnership.action_cancel()
        self.assertEqual(
            self.partner.commission_plan_id.id, plan_2.id,
            "Manually-set commission plan of partner should not be affected by partnership cancellation.",
        )
