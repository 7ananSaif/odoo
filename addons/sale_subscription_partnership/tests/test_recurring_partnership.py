# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from .common import SubscriptionsPartnershipCommon


class TestSubscriptionsPartnership(SubscriptionsPartnershipCommon):

    def test_basic_subscriptions_flow_with_partnership(self):
        self.sale_order_partnership.action_confirm()
        self.sale_order_partnership.next_invoice_date += relativedelta(months=1)
        self.assertEqual(
            self.partner.specific_property_product_pricelist,
            self.partnership_product.grade_id.default_pricelist_id,
            "Selling the partnership should assign the pricelist to the partner",
        )
        self.assertEqual(
            self.partner.grade_id,
            self.partnership_product.grade_id,
            "Selling the partnership should assign the grade to the partner",
        )
        self.sale_order_partnership.action_cancel()
        self.assertFalse(
            self.partner.specific_property_product_pricelist,
            "Cancelling the partnership order should remove the pricelist from the partner",
        )
        self.assertFalse(
            self.partner.grade_id,
            "Cancelling the partnership order should remove the grade from the partner",
        )
        action = self.sale_order_partnership.prepare_renewal_order()
        renewal_so = self.env['sale.order'].browse(action['res_id'])
        renewal_so.action_confirm()
        self.assertEqual(
            self.partner.specific_property_product_pricelist,
            self.partnership_product.grade_id.default_pricelist_id,
            "Renewing the partnership should assign the pricelist to the partner",
        )
        self.assertEqual(
            self.partner.grade_id,
            self.partnership_product.grade_id,
            "Renewing the partnership should assign the grade to the partner",
        )
        renewal_so.set_close()
        self.assertFalse(
            self.partner.specific_property_product_pricelist,
            "Closing the partnership order should remove the pricelist from the partner",
        )
        self.assertFalse(
            self.partner.grade_id,
            "Closing the partnership order should remove the grade from the partner",
        )
        renewal_so.set_open()
        self.assertEqual(
            self.partner.specific_property_product_pricelist,
            self.partnership_product.grade_id.default_pricelist_id,
            "Reopening a valid partnership should assign the pricelist to the partner",
        )
        self.assertEqual(
            self.partner.grade_id,
            self.partnership_product.grade_id,
            "Reopening a valid partnership should assign the grade to the partner",
        )

    def test_unrelated_grade_and_pricelist_unaffected_by_order_cancellation(self):
        self.sale_order_partnership.action_confirm()
        new_pricelist = self.env['product.pricelist'].create({'name': "test pricelist"})
        self.partner.property_product_pricelist = new_pricelist.id
        self.partner.grade_id = self.env.ref('partnership.res_partner_grade_data_silver').id
        self.sale_order_partnership.action_cancel()
        self.assertEqual(
            self.partner.specific_property_product_pricelist,
            new_pricelist,
            "Pricelist of partner should not be affected by partnership cancellation if changed.",
        )
        self.assertEqual(
            self.partner.grade_id,
            self.env.ref('partnership.res_partner_grade_data_silver'),
            "Grade of partner should not be affected by partnership cancellation if changed.",
        )
