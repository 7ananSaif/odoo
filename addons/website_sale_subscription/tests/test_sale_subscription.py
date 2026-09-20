# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import Form, freeze_time, tagged

from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('post_install', '-at_install')
class TestSaleSubscription(TestSubscriptionCommon):

    def test_delivery_line_not_applied_prorata_discount(self):
        """Ensure delivery lines keep their original price and are not prorated in subscription invoices and upsell order."""
        with freeze_time("2025-09-15"):
            sub = self.subscription
            sub.plan_id.billing_first_day = True

            # Create a custom delivery product and carrier
            delivery_categ = self.env.ref('delivery.product_category_deliveries')
            delivery_product = self.env['product.product'].create({
                'name': "Carrier Product",
                'type': 'service',
                'recurring_invoice': True,
                'categ_id': delivery_categ.id,
                'sale_ok': False,
                'purchase_ok': False,
                'invoice_policy': 'order',
                'list_price': 5.0,
            })
            delivery = self.env['delivery.carrier'].create({
                'name': "Test Carrier",
                'fixed_price': 5.0,
                'delivery_type': 'fixed',
                'product_id': delivery_product.id,
            })

            # Add delivery to subscription order
            delivery_wizard = Form(self.env['choose.delivery.carrier'].with_context({
                'default_order_id': sub.id,
                'default_carrier_id': delivery.id,
            }))
            choose_delivery = delivery_wizard.save()
            choose_delivery.button_confirm()

            # Ensure carrier line is added on order
            delivery_line = sub.order_line.filtered(lambda ln: ln.product_id == delivery_product)
            self.assertTrue(delivery_line, "Carrier line should be added to the subscription order")

            # Confirm subscription order
            sub.action_confirm()
            self.assertEqual("2025-09-15", sub.next_invoice_date.strftime("%Y-%m-%d"), "On confirmation, next_invoice_date")
            self.assertEqual(delivery_line.price_total, 5, "Delivery product price should stay fixed before invoicing")

            # Generate prorated invoice
            inv = sub._create_recurring_invoice()
            inv_delivery_line = inv.invoice_line_ids.filtered(lambda ln: ln.product_id == delivery_product)
            self.assertEqual("2025-10-01", sub.next_invoice_date.strftime("%Y-%m-%d"),
                "After prorated period, next_invoice_date should move to the 1st day of the next month")
            # Verify delivery product not prorated
            self.assertEqual(inv_delivery_line.price_total, 5, "Delivery line should remain unchanged(not prorated) in the invoice")

            sub1 = sub.copy()
            sub1.plan_id.billing_first_day = False
            sub1.action_confirm()
            sub1._create_recurring_invoice()
        with freeze_time("2025-09-20"):
            action = sub1.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            upsell_delivery_line = upsell_so.order_line.filtered(lambda ln: ln.product_id == delivery_product)
            upsell_delivery_line.product_uom_qty = 1.0
            self.assertEqual(upsell_delivery_line.price_total, 5, "Delivery product price should stay fixed")
