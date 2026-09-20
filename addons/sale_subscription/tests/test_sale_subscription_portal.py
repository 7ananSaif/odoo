# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import HttpCase, tagged
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon

@tagged('post_install', '-at_install')
class TestSubscription(TestSubscriptionCommon, HttpCase):
    def test_pay_button_enabled_in_portal(self):
        # Check that the pay button is enabled when having only one payment provider enabled
        self.env['payment.provider'].search([]).write({'is_published': False})
        self.dummy_provider = self.env['payment.provider'].create({
            'name': "Dummy Provider",
            'code': 'none',
            'state': 'test',
            'is_published': True,
            'payment_method_ids': [Command.set([self.env.ref('payment.payment_method_unknown').id])],
            'allow_tokenization': True,
            'redirect_form_view_id': self.env['ir.ui.view'].search([('type', '=', 'qweb')], limit=1).id,
        })
        self.env.ref('payment.payment_method_unknown').write({
            'active': True,
            'support_tokenization': True,
        })
        sub = self.subscription
        sub.action_confirm()
        self.start_tour(self.subscription.get_portal_url(), 'test_sale_subscription_portal')

    def test_sale_subscription_invoice_access_portal(self):
        sub = self.subscription
        sub.action_confirm()
        invoice = sub._cron_recurring_create_invoice()
        res = self.url_open(f'/my/invoices/{invoice.id}?access_token={invoice.access_token}')
        self.assertEqual(res.status_code, 200)

    def test_visibility_of_display_payment_message_in_portal(self):
        """
        Check visibility of payment section in portal when subscription is closed
        and the plan set on that subscription is archived
        """
        self.provider.write({'payment_method_ids': [Command.set([self.payment_method_id])]})
        sub = self.subscription
        sub.plan_id.write({'active': False})
        sub.action_confirm()
        inv = sub._create_invoices()
        inv._post()
        sub.set_close()
        self.start_tour(self.subscription.get_portal_url(), 'test_sale_subscription_portal_payment')

    def test_subscription_so_preview_without_user_id(self):
        """Ensure the sale order preview works for a subscription created by a portal user without a user_id."""

        sale_order = self.env['sale.order'].create({
                'name': "Protal so",
                'is_subscription': True,
                'user_id': False,
                'partner_id': self.user_portal.partner_id.id,
                'plan_id': self.plan_month.id,
                'order_line': [Command.create({
                    'name': self.sub_product_tmpl.name,
                    'product_id': self.sub_product_tmpl.product_variant_ids.id,
                    'product_uom_qty': 2.0,
                    'price_unit': self.sub_product_tmpl.list_price,
                })]
            })
        sale_order.action_confirm()
        preview_vals = sale_order.action_preview_sale_order()
        url = preview_vals.get('url')
        self.assertEqual(self.url_open(url).status_code, 200, "Preview URL's response status should be 200")
