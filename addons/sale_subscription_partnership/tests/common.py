# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.partnership.tests.common import PartnershipCommon


class SubscriptionsPartnershipCommon(PartnershipCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partnership_product.recurring_invoice = True
        cls.sale_order_partnership.plan_id = cls.env.ref('sale_subscription.subscription_plan_month').id
