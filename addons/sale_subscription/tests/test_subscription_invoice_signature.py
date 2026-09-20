# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import freeze_time, tagged

from odoo.addons.account_accountant.tests.test_signature import TestInvoiceSignature
from odoo.addons.sale_subscription.tests.test_sale_subscription import TestSubscription


@tagged('post_install', '-at_install')
@freeze_time("2021-01-03")
class TestSubscriptionInvoiceSignature(TestInvoiceSignature, TestSubscription):
    def setUp(self):
        super().setUp()
        self.sale_subscription_cron = self.env.ref("sale_subscription.account_analytic_cron_for_invoice")
        self.another_user.group_ids += self.env.ref("sales_team.group_sale_salesman")
        self.subscription = self.env['sale.order'].with_user(self.another_user).create({
                'partner_id': self.partner_a.id,
                'company_id': self.company_data['company'].id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    Command.create({
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 2.0,
                        'price_unit': 12,
                    })],
        })
        self.subscription.with_user(self.another_user).action_confirm()

    def test_subscription_automated_invoice_should_have_signing_user_set_to_salesman(self):
        self.assertEqual(self.subscription.invoice_count, 0)
        with self.enter_registry_test_mode():
            self.sale_subscription_cron.method_direct_trigger()
        self.assertEqual(self.subscription.invoice_count, 1)
        inv = self.subscription.invoice_ids
        self.assertEqual(
            inv.signing_user,
            self.another_user,
            "When the invoice is posted by odoobot, the signer should be the one that confirmed the subscription"
        )

    def test_subscription_automated_invoice_should_have_signing_user_set_to_representative_when_there_is_one(self):
        representative_user = self.company_data['default_user_salesman']
        self.env.company.signing_user = representative_user  # set the representative user of the company
        self.assertEqual(self.subscription.invoice_count, 0)
        with self.enter_registry_test_mode():
            self.sale_subscription_cron.method_direct_trigger()
        self.assertEqual(self.subscription.invoice_count, 1)
        inv = self.subscription.invoice_ids
        self.assertEqual(
            inv.signing_user,
            representative_user,
            "Signer should be representative if available"
        )

    def test_renewed_churned_canceled(self):
        with freeze_time("2024-07-03"):
            subscription = self.env['sale.order'].with_context(self.context_no_mail).create({
                'name': 'TestSubscription',
                'is_subscription': True,
                'plan_id': self.plan_month.id,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'sale_order_template_id': self.subscription_tmpl.id,
            })
            subscription._onchange_sale_order_template_id()
            subscription.start_date = False
            subscription.end_date = False
            self.flush_tracking()
            subscription.action_confirm()
            self.flush_tracking()
            subscription._create_recurring_invoice()
            self.assertEqual(subscription.invoice_count, 1)
        with freeze_time("2024-08-03"):
            action = subscription.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            self.flush_tracking()
            renewal_so.action_confirm()
            self.flush_tracking()
        with freeze_time("2024-09-03"):
            # customer never pays (happens when the token is not working).
            renewal_so.sudo()._cron_subscription_expiration()
            self.flush_tracking()
            self.assertEqual(renewal_so.subscription_state, '6_churn')
            self.assertEqual(subscription.subscription_state, '5_renewed')
            with self.assertRaises(ValidationError):
                # You cannot cancel a churned renewed subscription. You can reopen it and cancel it if you want to reopen the parent
                renewal_so._action_cancel()
            renewal_so.reopen_order()
            renewal_so._action_cancel()
            self.assertFalse(renewal_so.subscription_state, "renewal is canceled")
            self.assertEqual(renewal_so.state, 'cancel', "renewal is canceled")
            self.assertEqual(subscription.subscription_state, '3_progress')

    def test_sale_order_log_creation(self):
        """ Test that duplicating a canceled quotation is possible
        """
        with freeze_time("2024-07-30"):
            self.subscription.write({
                        'start_date': False,
                        'next_invoice_date': False,
            })
            self.subscription._onchange_sale_order_template_id()
            self.subscription._action_cancel()
            self.assertFalse(self.subscription.subscription_state)
            sub = self.subscription.copy()
            self.assertEqual(sub.subscription_state, '1_draft')
            self.assertEqual(sub.state, 'draft')
        with freeze_time("2024-07-31"):
            self.flush_tracking()
            sub.action_confirm()
            self.flush_tracking()
            self.assertEqual(sub.subscription_state, '3_progress')
            self.assertFalse(self.subscription.subscription_state)
            log = sub.order_log_ids
            self.assertEqual(len(log), 1)
            self.assertEqual(log.event_type, '0_creation')
            self.assertEqual(log.subscription_state, '1_draft')

    def test_recurring_create_invoice_branch(self):
        self.company.child_ids = [Command.create({'name': 'Branch'})]
        branch = self.company.child_ids[0]
        product = self.product.copy({'company_id': branch.id})
        sub = self.env['sale.order'].with_company(branch).create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'partner_id': self.user_portal.partner_id.id,
            'order_line': [(0, 0, {'product_id': product.id})],
        })
        sub.action_confirm()
        self.env['sale.order']._cron_recurring_create_invoice()

        self.assertEqual(sub.invoice_count, 1)
        self.assertEqual(sub.invoice_ids.company_id, branch)
        self.assertEqual(sub.invoice_ids.state, 'posted')

    def test_sale_determine_order(self):
        """ If a subscription order is locked but has a renewal (child order), an attempt to
        expense some purchase order which is linked to the analytic account of the subscription
        should use the non-locked, renewed order.
        """
        required_modules = ('project_hr_expense', 'purchase')
        if not all(self.env['ir.module.module']._get(module).state == 'installed' for module in required_modules):
            self.skipTest(f'This test requires the installation of the following modules: {required_modules}')

        analytic_plan = self.env['account.analytic.plan'].create({'name': 'TSDO analytic plan'})
        analytic_account1, analytic_account2 = self.env['account.analytic.account'].create([{
            'name': f'TSDO analytic account {i}',
            'plan_id': analytic_plan.id,
        } for i in (1, 2)])

        project = self.env['project.project'].sudo().with_context({'mail_create_nolog': True}).create({
            'name': 'Project',
            'partner_id': self.partner_a.id,
            'account_id': analytic_account1.id,
        })
        recurring_service_with_linked_project = self.env['product.product'].create({
            'name': 'service_with_linked_project',
            'standard_price': 30,
            'list_price': 90,
            'type': 'service',
            'service_tracking': 'task_global_project',
            'project_id': project.id,
            'recurring_invoice': True,
        })
        expensable_service_product = self.env['product.product'].create({
            'name': 'Material',
            'type': 'service',
            'standard_price': 5,
            'list_price': 10,
            'can_be_expensed': True,
            'expense_policy': 'sales_price',
            'purchase_method': 'purchase',
        })
        subscription1, subscription2 = self.env['sale.order'].create([{
            'name': 'TestSubscription',
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'partner_id': self.partner_a.id,
            'order_line': [(0, 0, {
                'product_id': recurring_service_with_linked_project.id,
                'product_uom_qty': 1,
                'price_unit': 10,
            })],
            'project_account_id': analytic_account_id,
        } for analytic_account_id in [analytic_account1.id, analytic_account2.id]])
        purchase_order = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [(0, 0, {
                'product_id': expensable_service_product.id,
                'product_uom_qty': 1,
                'analytic_distribution': {analytic_account1.id: 100.0},
            }), (0, 0, {
                'product_id': expensable_service_product.id,
                'product_uom_qty': 1,
                'analytic_distribution': {analytic_account2.id: 100.0},
            })],
        })
        subscriptions = subscription1 + subscription2
        subscriptions.action_confirm()
        subscriptions._create_invoices()
        subscriptions.invoice_ids[0].action_post()
        subscription1.prepare_renewal_order()
        subscription2.prepare_renewal_order()
        first_renewal_sub1 = subscription1.subscription_child_ids[0]
        first_renewal_sub1.action_confirm()
        first_renewal_sub1.action_cancel()
        subscription1.subscription_state = '3_progress'
        subscription1.prepare_renewal_order()
        second_renewal_sub1 = subscription1.subscription_child_ids.filtered(lambda so: so.state == 'draft')
        second_renewal_sub1.action_confirm()
        second_renewal_sub1._create_invoices()
        second_renewal_sub1.invoice_ids.filtered(lambda am: am.state == 'draft').action_post()
        second_renewal_sub1.prepare_renewal_order()
        second_renewal_renewal_sub1 = second_renewal_sub1.subscription_child_ids[0]
        second_renewal_renewal_sub1.action_confirm()

        purchase_order.button_confirm()
        purchase_order.action_create_invoice()
        purchase_order_invoice = purchase_order.invoice_ids[0]
        purchase_order_invoice.invoice_date = '2000-05-05'
        purchase_order_invoice.action_post()

        self.assertEqual(purchase_order_invoice.state, 'posted')

    def test_uspell_same_product_different_discount(self):
        subscription = self.env['sale.order'].create({
            'name': 'Original subscription',
            'is_subscription': True,
            'partner_id': self.user_portal.partner_id.id,
            'plan_id': self.plan_month.id,
            'order_line': [
                Command.create({
                    'name': self.product2.name,
                    'product_id': self.product2.id,
                    'product_uom_qty': 1,
                    'discount': 0,
                }),
                Command.create({
                    'name': self.product2.name,
                    'product_id': self.product2.id,
                    'product_uom_qty': 1,
                    'discount': 50,
                })
            ]
        })

        subscription.action_confirm()
        self.env['sale.order']._cron_recurring_create_invoice()
        action = subscription.prepare_upsell_order()
        upsell = self.env['sale.order'].browse(action['res_id'])
        self.assertEqual(set(upsell.order_line.mapped('discount')), {0, 50}, 'Upsell discounts should match subscription discounts')
