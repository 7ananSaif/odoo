# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import freeze_time, tagged
from odoo.tools import mute_logger

from odoo.addons.sale_subscription.models.sale_order import SaleOrder
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('post_install', '-at_install')
class TestSubscriptionRenew(TestSubscriptionCommon):

    @classmethod
    def default_env_context(cls):
        return {}

    @mute_logger('odoo.models.unlink')
    def test_renewal(self):
        """ Test subscription renewal """
        with freeze_time("2021-11-18"):
            # We reset the renew alert to make sure it will run with freezetime
            self.subscription.write({
                'start_date': False,
                'next_invoice_date': False,
                'partner_invoice_id': self.partner_a_invoice.id,
                'partner_shipping_id': self.partner_a_shipping.id,
                'internal_note': 'internal note',
            })            # add an so line with a different uom
            uom_dozen = self.env.ref('uom.product_uom_dozen').id
            self.subscription_tmpl.duration_value = 2 # end after 2 months to adapt to the following line
            self.subscription_tmpl.duration_unit = 'month'
            self.env['sale.order.line'].create({'name': self.product.name,
                                                'order_id': self.subscription.id,
                                                'product_id': self.product3.id,
                                                'product_uom_qty': 4,
                                                'product_uom_id': uom_dozen,
                                                'price_unit': 42})

            self.subscription.action_confirm()
            self.subscription._create_recurring_invoice()
            self.assertEqual(self.subscription.end_date, datetime.date(2022, 1, 17), 'The end date of the subscription should be updated according to the template')
            self.assertEqual(self.subscription.next_invoice_date, datetime.date(2021, 12, 18))
            self.env['account.payment.register'] \
                .with_context(active_model='account.move', active_ids=self.subscription.invoice_ids.ids) \
                .create({
                'currency_id': self.subscription.currency_id.id,
                'amount': self.subscription.amount_total,
            })._create_payments()
            self.assertEqual(self.subscription.invoice_count, 1)

        self.assertTrue(self.subscription.invoice_ids.payment_state in ['in_payment', 'paid'], "the invoice is considered paid, depending on the settings.")

        with freeze_time("2021-12-18"):
            action = self.subscription.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            self.assertEqual(renewal_so.partner_invoice_id, self.partner_a_invoice)
            self.assertEqual(renewal_so.partner_shipping_id, self.partner_a_shipping)
            # check produt_uom_qty
            self.assertEqual(renewal_so.sale_order_template_id.id, self.subscription.sale_order_template_id.id,
                             'sale_subscription: renewal so should have the same template')

            renewal_start_date = renewal_so.start_date
            with self.assertRaises(ValidationError):
                # try to start the renewal before the parent next invoice date
                renewal_so.start_date = self.subscription.next_invoice_date - relativedelta(days=1)
                renewal_so.action_confirm()
            renewal_so.start_date = renewal_start_date
            renewal_so.action_confirm()

            self.assertEqual(renewal_so.internal_note_display, Markup('<p>internal note</p>'), 'Internal Note should redirect to the parent')
            self.assertEqual(self.subscription.recurring_monthly, 189, 'Should be closed but with an MRR')
            self.assertEqual(renewal_so.subscription_state, '3_progress', 'so should now be in progress')
            self.assertEqual(self.subscription.subscription_state, '5_renewed')
            self.assertEqual(renewal_so.date_order.date(), self.subscription.end_date, 'renewal start date should depends on the parent end date')
            self.assertEqual(renewal_so.start_date, self.subscription.end_date, 'The renewal subscription start date and the renewed end_date should be aligned')

            self.assertEqual(renewal_so.plan_id, self.plan_month, 'the plan should be propagated')
            self.assertEqual(renewal_so.next_invoice_date, datetime.date(2021, 12, 18))
            self.assertEqual(renewal_so.start_date, datetime.date(2021, 12, 18))
            self.assertTrue(renewal_so.is_subscription)
            renewal_so._create_recurring_invoice()

        with freeze_time("2024-11-17"):
            invoice = self.subscription._create_recurring_invoice()
            self.assertFalse(invoice, "Locked contract should not generate invoices")
            renewal_so.internal_note_display = 'new internal note'
            self.assertEqual(renewal_so.internal_note_display, Markup('<p>new internal note</p>'), 'Internal Note should be updated')
            self.assertEqual(self.subscription.internal_note_display, Markup('<p>new internal note</p>'), 'Internal Note should be updated')
        with freeze_time("2024-11-19"):
            self.subscription._create_recurring_invoice() # it will close self.subscription
            renew_close_reason_id = self.env.ref('sale_subscription.close_reason_renew').id
            self.assertEqual(self.subscription.subscription_state, '5_renewed')
            self.assertEqual(self.subscription.close_reason_id.id, renew_close_reason_id)
            (self.subscription | renewal_so).invalidate_recordset(['invoice_ids', 'invoice_count'])
            self.assertEqual(self.subscription.invoice_count, 2)
            self.assertEqual(renewal_so.invoice_count, 2)

    def test_renew_kpi_mrr(self):
        # Test that renew with MRR transfer give correct result
        # First, whe create a sub with MRR = 21
        # Then we renew it with a MRR of 42
        # After a few months the MRR of the renewal is 63
        # We also create and renew a free subscription

        with freeze_time("2021-01-01"), patch.object(SaleOrder, '_get_unpaid_subscriptions', lambda x: []):
            self.subscription.plan_id.auto_close_limit = 5000  # don't close automatically contract if unpaid invoices
            # so creation with mail tracking
            context_mail = {'tracking_disable': False}
            sub = self.env['sale.order'].with_context(context_mail).create({
                'name': 'Parent Sub',
                'is_subscription': True,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'sale_order_template_id': self.subscription_tmpl.id,
            })
            free_sub = self.env['sale.order'].with_context(context_mail).create({
                'name': 'Parent free Sub',
                'is_subscription': True,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'plan_id': self.plan_month.id,
                'client_order_ref': 'free',
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 3.0,
                        'price_unit': 0,
                    })],
            })

            future_sub = self.env['sale.order'].with_context(context_mail).create({
                'name': 'FutureSub',
                'is_subscription': True,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'plan_id': self.plan_month.id,
                'start_date': '2021-06-01',
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 1.0,
                    })],
            })

            self.assertFalse(free_sub.amount_total)
            self.flush_tracking()
            sub._onchange_sale_order_template_id()
            # Same product for both lines
            sub.order_line.product_uom_qty = 1
            (free_sub | sub).end_date = datetime.date(2022, 1, 1)
            (free_sub | sub | future_sub).action_confirm()
            self.flush_tracking()
            self.assertEqual(sub.recurring_monthly, 21, "20 + 1 for both lines")
            self.assertEqual(sub.subscription_state, "3_progress")
            self.env['sale.order'].with_context(tracking_disable=False)._cron_recurring_create_invoice()
        with freeze_time("2021-02-01"):
            self.env['sale.order'].with_context(tracking_disable=False)._cron_recurring_create_invoice()
        with freeze_time("2021-03-01"):
            self.env['sale.order'].with_context(tracking_disable=False)._cron_recurring_create_invoice()
        with freeze_time("2021-04-01"):
            # We create a renewal order in april for the new year
            self.env['sale.order']._cron_recurring_create_invoice()
            action = sub.with_context(tracking_disable=False).prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so = renewal_so.with_context(tracking_disable=False)
            renewal_so.order_line.product_uom_qty = 3
            renewal_so.name = "Renewal"
            self.flush_tracking()
            action = free_sub.with_context(tracking_disable=False).prepare_renewal_order()
            free_renewal_so = self.env['sale.order'].browse(action['res_id'])
            free_renewal_so = free_renewal_so.with_context(tracking_disable=False)
            free_renewal_so.order_line.write({'product_uom_qty': 2, 'price_unit': 0})
            self.flush_tracking()
            self.assertEqual(renewal_so.subscription_state, '2_renewal')
            (sub | free_sub).pause_subscription() # we pause the contracts to make sure no parasite log are created
            self.flush_tracking()
            self.env['sale.order']._cron_recurring_create_invoice()
            self.flush_tracking()
            (renewal_so | free_renewal_so).action_confirm()
            self.flush_tracking()
            self.assertEqual(sub.subscription_state, '5_renewed')
            self.assertEqual(renewal_so.subscription_state, '3_progress')
            (sub | free_sub).resume_subscription() # we resume the contracts to make sure no parasite log are created
            self.flush_tracking()
            # Most of the time, the renewal invoice is created by the salesman
            # before the renewal start date
            renewal_invoices = (free_renewal_so | renewal_so)._create_invoices()
            renewal_invoices._post()
            self.flush_tracking()
            # "upsell" of the simple sub that did not start yet
            future_sub.order_line.product_uom_qty = 4
            self.flush_tracking()
            self.assertEqual(sub.recurring_monthly, 21, "MRR should still be non null")
            self.assertEqual(sub.subscription_state, '5_renewed')
            self.assertEqual(renewal_so.recurring_monthly, 63, "MRR of renewal should not be computed before start_date of the lines")
            self.flush_tracking()
            # renew is still not ongoing;  Total MRR is 21 coming from the original sub
            self.env['sale.order'].sudo()._cron_subscription_expiration()
            self.assertEqual(sub.recurring_monthly, 21)
            self.assertEqual(renewal_so.recurring_monthly, 63)
            self.env['sale.order']._cron_recurring_create_invoice()
            self.flush_tracking()
            self.subscription._cron_update_kpi()
            self.assertEqual(sub.kpi_1month_mrr_delta, 0)
            self.assertEqual(sub.kpi_1month_mrr_percentage, 0)
            self.assertEqual(sub.kpi_3months_mrr_delta, 0)
            self.assertEqual(sub.kpi_3months_mrr_percentage, 0)
            self.assertEqual(sub.subscription_state, '5_renewed')

        with freeze_time("2021-04-20"):
            # We upsell the renewal after it's confirmation but before its start_date The event date must be "today"
            self.flush_tracking()
            renewal_so.order_line[1].product_uom_qty += 1
            self.flush_tracking()

        with freeze_time("2021-05-05"): # We switch the cron the X of may to make sure the day of the cron does not affect the numbers
            # Renewal period is from 2021-05 to 2021-06
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(sub.recurring_monthly, 21)
            self.assertEqual(sub.subscription_state, '5_renewed')
            self.assertEqual(renewal_so.next_invoice_date, datetime.date(2021, 6, 1))
            self.assertEqual(renewal_so.recurring_monthly, 83)
            self.flush_tracking()

        with freeze_time("2021-05-15"):
            self.env['sale.order']._cron_recurring_create_invoice()
            sub.order_line._compute_recurring_monthly()
            self.flush_tracking()

        with freeze_time("2021-06-01"):
            self.subscription._cron_update_kpi()
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(sub.recurring_monthly, 21)
            self.assertEqual(renewal_so.recurring_monthly, 83)
            self.flush_tracking()

        with freeze_time("2021-07-01"), patch.object(SaleOrder, '_get_unpaid_subscriptions', lambda x: []):
            # Total MRR is 42 coming from renew
            self.subscription._cron_update_kpi()
            self.env['sale.order']._cron_recurring_create_invoice()
            self.env['sale.order']._cron_subscription_expiration()
            # we trigger the compute because it depends on today value.
            self.assertEqual(sub.recurring_monthly, 21)
            self.assertEqual(renewal_so.recurring_monthly, 83)
            self.flush_tracking()

        with freeze_time("2021-08-03"), patch.object(SaleOrder, '_get_unpaid_subscriptions', lambda x: []):
            # We switch the cron the X of august to make sure the day of the cron does not affect the numbers
            renewal_so.end_date = datetime.date(2032, 1, 1)
            self.flush_tracking()
            # Total MRR is 80 coming from renewed sub
            self.env['sale.order']._cron_recurring_create_invoice()
            self.env['sale.order'].sudo()._cron_subscription_expiration()
            self.assertEqual(sub.recurring_monthly, 21)
            self.assertEqual(renewal_so.recurring_monthly, 83)
            self.assertEqual(sub.subscription_state, '5_renewed')
            self.flush_tracking()
        with freeze_time("2021-09-01"), patch.object(SaleOrder, '_get_unpaid_subscriptions', lambda x: []):
            renewal_so.order_line.product_uom_qty = 5
            # We update the MRR of the renewed
            self.env['sale.order']._cron_recurring_create_invoice()
            self.env['sale.order']._cron_subscription_expiration()
            self.assertEqual(renewal_so.recurring_monthly, 105)
            # free subscription is not free anymore
            free_renewal_so.order_line.price_unit = 10
            self.flush_tracking()
            self.subscription._cron_update_kpi()
            self.assertEqual(sub.kpi_1month_mrr_delta, 0)
            self.assertEqual(sub.kpi_1month_mrr_percentage, 0)
            self.assertEqual(sub.kpi_3months_mrr_delta, 0)
            self.assertEqual(sub.kpi_3months_mrr_percentage, 0)
            self.assertEqual(renewal_so.kpi_1month_mrr_delta, 22)
            self.assertEqual(round(renewal_so.kpi_1month_mrr_percentage, 2), 0.27)
            self.assertEqual(renewal_so.kpi_3months_mrr_delta, 22)
            self.assertEqual(round(renewal_so.kpi_3months_mrr_percentage, 2), 0.27)

        order_log_ids = sub.order_log_ids.sorted('event_date')
        sub_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly) for log in order_log_ids]
        self.assertEqual(sub_data, [('0_creation', datetime.date(2021, 1, 1), '1_draft', 21, 21),
                                    ('3_transfer', datetime.date(2021, 4, 1), '5_renewed', -21, 0)])
        renew_logs = renewal_so.order_log_ids.sorted(key=lambda log: (log.event_date, log.id))
        renew_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly) for log in renew_logs]
        self.assertEqual(renew_data, [('3_transfer', datetime.date(2021, 4, 1), '2_renewal', 21.0, 21.0),
                                      ('1_expansion', datetime.date(2021, 4, 1), '3_progress', 42.0, 63.0),
                                      ('1_expansion', datetime.date(2021, 4, 20), '3_progress', 20.0, 83.0),
                                      ('1_expansion', datetime.date(2021, 9, 1), '3_progress', 22, 105.0)])
        self.assertEqual(renewal_so.start_date, datetime.date(2021, 5, 1), "the renewal starts on the firsts of May even if transfer occurs on first of April")
        free_log_ids = free_sub.order_log_ids.sorted(key=lambda log: (log.event_date, log.id))
        sub_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly) for log in
                    free_log_ids]
        self.assertEqual(sub_data, [('0_creation', datetime.date(2021, 1, 1), '1_draft', 0, 0),
                                    ('3_transfer', datetime.date(2021, 4, 1), '5_renewed', 0, 0)])
        renew_logs = free_renewal_so.order_log_ids.sorted(key=lambda log: (log.event_date, log.id))
        renew_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly) for log
                      in renew_logs]
        self.assertEqual(renew_data, [('3_transfer', datetime.date(2021, 4, 1), '2_renewal', 0, 0),
                                      ('1_expansion', datetime.date(2021, 9, 1), '3_progress', 20.0, 20.0)])

        future_data = future_sub.order_log_ids.sorted(key=lambda log: (log.event_date, log.id)) # several events aggregated on the same date
        simple_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly) for log
                       in future_data]
        self.assertEqual(simple_data, [('0_creation', datetime.date(2021, 1, 1), '1_draft', 1.0, 1.0),
                                       ('1_expansion', datetime.date(2021, 4, 1), '3_progress', 3.0, 4.0)])
        self.assertEqual(future_sub.start_date, datetime.date(2021, 6, 1), "the start date is in june but the events are recorded as today")

    def test_multiple_renew(self):
        """ Prevent to confirm several renewal quotation for the same subscription """
        self.subscription.write({'start_date': False, 'next_invoice_date': False})
        self.subscription.action_confirm()
        self.subscription._cron_recurring_create_invoice()
        action = self.subscription.prepare_renewal_order()
        renewal_so_1 = self.env['sale.order'].browse(action['res_id'])
        action = self.subscription.prepare_renewal_order()
        renewal_so_2 = self.env['sale.order'].browse(action['res_id'])
        renewal_so_1.action_confirm()
        self.assertEqual(renewal_so_2.state, 'cancel', 'The other quotation should be canceled')

    def test_renew_different_currency(self):
        with freeze_time("2023-03-28"):
            self.product.subscription_rule_ids.unlink()
            default_pricelist = self.pricelist
            other_currency = self._enable_currency('EUR')
            other_pricelist = self.env['product.pricelist'].create({
                'name': 'Test Pricelist (EUR)',
                'currency_id': other_currency.id,
            })
            other_currency.write({
                'rate_ids': [(0, 0, {
                    'rate': 20,
                })]
            })
            pricing_month_1 = self.env['product.pricelist.item'].create({
                'plan_id': self.plan_month.id,
                'fixed_price': 10,
                'pricelist_id': default_pricelist.id,
            })
            pricing_month_2 = self.env['product.pricelist.item'].create({
                'plan_id': self.plan_month.id,
                'fixed_price': 200,
                'pricelist_id': other_pricelist.id,
            })
            sub_product_tmpl = self.env['product.template'].create({
                'name': 'BaseTestProduct',
                'type': 'service',
                'recurring_invoice': True,
                'uom_id': self.env.ref('uom.product_uom_unit').id,
                'subscription_rule_ids': [(6, 0, (pricing_month_1 | pricing_month_2).ids)]
            })
            subscription_tmpl = self.env['sale.order.template'].create({
                'name': 'Subscription template without discount',
                'duration_unit': 'year',
                'is_unlimited': False,
                'duration_value': 2,
                'note': "This is the template description",
                'plan_id': self.plan_month.copy(default={'auto_close_limit': 5}).id,
                'sale_order_template_line_ids': [Command.create({
                    'name': "Product 1",
                    'product_id': sub_product_tmpl.product_variant_id.id,
                    'product_uom_qty': 1,
                    'product_uom_id': sub_product_tmpl.product_variant_id.uom_id.id,
                })]
            })
            sub = self.subscription.create({
                'name': 'Company1 - Currency1',
                'sale_order_template_id': subscription_tmpl.id,
                'partner_id': self.user_portal.partner_id.id,
                'currency_id': self.company.currency_id.id,
                'plan_id': self.plan_month.id,
                'order_line': [(0, 0, {
                    'name': "Product 1",
                    'product_id': sub_product_tmpl.product_variant_id.id,
                    'product_uom_qty': 1,
                })]
            })
            sub.pricelist_id = default_pricelist.id
            sub._onchange_sale_order_template_id() # recompute the pricings
            self.flush_tracking()
            sub.action_confirm()
            self.assertEqual(sub.recurring_monthly, 10)
            self.flush_tracking()
            self.env['sale.order']._cron_recurring_create_invoice()
            self.flush_tracking()

        with freeze_time("2023-04-29"):
            action = sub.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so.write({
                'pricelist_id': other_pricelist.id,
            })
            renewal_so._onchange_sale_order_template_id()
            renewal_so.order_line.product_uom_qty = 3
            self.flush_tracking()
            renewal_so.action_confirm()
            self.flush_tracking()
            self.env['sale.order']._cron_recurring_create_invoice()
            order_log_ids = sub.order_log_ids.sorted(key=lambda log: (log.event_date, log.id))
            sub_data = [(log.event_type, log.event_date, log.amount_signed, log.recurring_monthly, log.currency_id)
                        for log in order_log_ids]
            self.assertEqual(sub_data,
                             [('0_creation', datetime.date(2023, 3, 28), 10, 10, default_pricelist.currency_id),
                              ('3_transfer', datetime.date(2023, 4, 29), -10, 0, default_pricelist.currency_id)
                              ])

            renew_logs = renewal_so.order_log_ids.sorted(key=lambda log: (log.event_date, log.id))
            renew_data = [(log.event_type, log.event_date, log.amount_signed, log.recurring_monthly, log.currency_id)
                          for log in renew_logs]
            self.assertEqual(renew_data, [
                ('3_transfer', datetime.date(2023, 4, 29), 200, 200, other_currency),
                ('1_expansion', datetime.date(2023, 4, 29), 400, 600, other_currency)
            ])

    def test_renewal_churn(self):
        # Test what we expect when we
        # 1) create a renewal quote
        # 2) close the parent
        # 3) confirm the renewal

        with freeze_time("2021-01-01"), patch.object(SaleOrder, '_get_unpaid_subscriptions', lambda x: []):
            # so creation with mail tracking
            context_mail = {'tracking_disable': False}
            sub = self.env['sale.order'].with_context(context_mail).create({
                'name': 'Parent Sub',
                'is_subscription': True,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'sale_order_template_id': self.subscription_tmpl.id,
            })
            sub._onchange_sale_order_template_id()
            # Same product for both lines
            sub.order_line.product_uom_qty = 1
            self.flush_tracking()
            sub.action_confirm()
            sub._create_recurring_invoice()
            self.flush_tracking()
            action = sub.with_context(tracking_disable=False).prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so = renewal_so.with_context(tracking_disable=False)
            renewal_so.order_line.product_uom_qty = 3
            renewal_so.name = "Renewal"
            self.flush_tracking()
            sub.set_close()
            self.flush_tracking()
            renewal_so.action_confirm()
            self.flush_tracking()

            order_log_ids = sub.order_log_ids.sorted('id')
            sub_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly)
                        for log in order_log_ids]
            self.assertEqual(sub_data,
                             [('0_creation', datetime.date(2021, 1, 1), '1_draft', 21.0, 21.0),
                              ('3_transfer', datetime.date(2021, 1, 1), '5_renewed', -21.0, 0.0)])
            order_log_ids = renewal_so.order_log_ids.sorted('id')
            renew_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly) for log in order_log_ids]
            self.assertEqual(renew_data, [('3_transfer', datetime.date(2021, 1, 1), '2_renewal', 21, 21),
                                          ('1_expansion', datetime.date(2021, 1, 1), '3_progress', 42.0, 63)])

    def test_churn_log_renew(self):
        """ Test the behavior of the logs when we confirm a renewal quote after the parent has been closed.
        """
        self.flush_tracking()
        with freeze_time("2024-01-22 08:00:00"):
            today = datetime.date.today()
            context_mail = {'tracking_disable': False}
            sub = self.env['sale.order'].with_context(context_mail).create({
                'name': 'TestSubscription',
                'is_subscription': True,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'sale_order_template_id': self.subscription_tmpl.id,
            })
            sub._onchange_sale_order_template_id()
            # Same product for both lines
            sub.order_line.product_uom_qty = 1
            self.flush_tracking()
            sub.action_confirm()
            self.flush_tracking()
            sub.order_line.product_uom_qty = 2
            self.flush_tracking()

            self.env['sale.order'].with_context(tracking_disable=False)._cron_recurring_create_invoice()
            self.flush_tracking()
            action = sub.with_context(tracking_disable=False).prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so = renewal_so.with_context(tracking_disable=False)
            renewal_so.order_line.product_uom_qty = 3
            renewal_so.name = "Renewal"
            self.flush_tracking()
            sub.set_close()
            self.flush_tracking()
            renewal_so.action_confirm()
            self.flush_tracking()
            # Most of the time, the renewal invoice is created by the salesman
            # before the renewal start date
            renewal_invoices = renewal_so._create_invoices()
            renewal_invoices._post()
            order_log_ids = sub.order_log_ids.sorted('id')
            sub_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly) for log in
                        order_log_ids]
            self.assertEqual(sub_data, [('0_creation', today, '1_draft', 21, 21),
                                        ('1_expansion', today, '3_progress', 21.0, 42.0),
                                        ('3_transfer', today, '5_renewed', -42, 0)])
            renew_logs = renewal_so.order_log_ids.sorted('id')
            renew_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly) for log
                        in renew_logs]
            self.assertEqual(sub.subscription_state, '5_renewed')
            self.assertEqual(renew_data, [('3_transfer', today, '2_renewal', 42, 42),
                                        ('1_expansion', today, '3_progress', 21.0, 63.0)])

    def test_renewal_different_period(self):
        """ When a renewal quote is negotiated for more than a month, we need to update the start date of the
        renewal quote if the parent is prolonged.
        """
        with freeze_time("2023-01-01"):
            # We reset the renew alert to make sure it will run with freezetime
            self.subscription.write({'start_date': False, 'next_invoice_date': False})
            self.subscription._onchange_sale_order_template_id()
            self.assertEqual(self.subscription.plan_id, self.plan_month)
            self.subscription.action_confirm()
            self.subscription._create_recurring_invoice()
            action = self.subscription.with_context(tracking_disable=False).prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so = renewal_so.with_context(tracking_disable=False)
            renewal_so.order_line.product_uom_qty = 3
            renewal_so.name = "Renewal"
            renewal_so.plan_id = self.plan_year
            self.assertEqual(self.subscription.next_invoice_date, datetime.date(2023, 2, 1))
            self.assertEqual(renewal_so.start_date, datetime.date(2023, 2, 1))
            self.assertEqual(renewal_so.next_invoice_date, datetime.date(2023, 2, 1))
        with freeze_time("2023-02-01"):
            # the new invoice is created and validated by the customer
            self.subscription._create_recurring_invoice()
            self.assertEqual(self.subscription.next_invoice_date, datetime.date(2023, 3, 1))
            self.assertEqual(renewal_so.start_date, datetime.date(2023, 3, 1))
            self.assertEqual(renewal_so.next_invoice_date, datetime.date(2023, 3, 1))

    def test_renew_with_different_currency(self):
        pricelist_eur = self.env['product.pricelist'].create({
            'name': 'Euro pricelist',
            'currency_id': self.env.ref('base.EUR').id,
        })
        self.sub_product_tmpl.subscription_rule_ids.filtered(
            lambda rule: rule.plan_id == self.plan_month
        ).fixed_price = 42
        pricing_month_eur = self.env['product.pricelist.item'].create({
            'plan_id': self.plan_month.id,
            'pricelist_id': pricelist_eur.id,
            'fixed_price': 420,
            'product_tmpl_id': self.sub_product_tmpl.id,
        })
        self.sub_product_tmpl.subscription_rule_ids = [Command.link(pricing_month_eur.id)]

        self.subscription_tmpl.sale_order_template_line_ids[1].unlink()
        self.subscription.order_line.product_id.taxes_id = [Command.clear()]
        self.subscription._onchange_sale_order_template_id()
        self.subscription.action_confirm()
        self.assertEqual(self.subscription.amount_total, 42)
        self.subscription._create_recurring_invoice()
        action = self.subscription.prepare_renewal_order()
        renew_so = self.env['sale.order'].browse(action['res_id'])
        self.assertEqual(renew_so.amount_total, 42)
        renew_so.pricelist_id = pricelist_eur.id
        renew_so.action_update_prices()
        self.assertEqual(renew_so.amount_total, 420)

    def test_renew_pricelist_currency_update(self):
        """
        Assert that after renewing a subscription, changing the pricelist
        to another one will recompute the order lines pricings.
        """
        with freeze_time("2023-04-04"):
            default_pricelist = self.pricelist
            other_currency = self._enable_currency('EUR')
            other_pricelist = self.env['product.pricelist'].create({
                'name': 'Test Pricelist (EUR)',
                'currency_id': other_currency.id,
            })
            other_currency.rate_ids = [Command.create({'rate': 20})]
            pricing_month_1_usd = self.env['product.pricelist.item'].create({
                'plan_id': self.plan_month.id,
                'fixed_price': 100,
                'pricelist_id': default_pricelist.id,
            })
            pricing_month_2_eur = self.env['product.pricelist.item'].create({
                'plan_id': self.plan_month.id,
                'fixed_price': 200,
                'pricelist_id': other_pricelist.id,
            })
            sub_product_tmpl = self.env['product.template'].create({
                'name': 'BaseTestProduct',
                'type': 'service',
                'recurring_invoice': True,
                'uom_id': self.env.ref('uom.product_uom_unit').id,
                'subscription_rule_ids': [Command.set((pricing_month_1_usd | pricing_month_2_eur).ids)]
            })
            sub = self.subscription.create({
                'name': 'Company1 - Currency1',
                'partner_id': self.user_portal.partner_id.id,
                'currency_id': self.company.currency_id.id,
                'plan_id': self.plan_month.id,
                'pricelist_id': default_pricelist.id,
                'order_line': [Command.create({
                    'name': "Product 1",
                    'product_id': sub_product_tmpl.product_variant_id.id,
                    'product_uom_qty': 1,
                })]
            })
            sub.action_confirm()
            self.flush_tracking()

            # Assert that order line was created with correct pricing and currency.
            self.assertEqual(sub.order_line[0].price_unit, 100.0, "Subscription product's order line must be created with default pricelist pricing (USD) having the price unit as 100.0.")
            self.assertEqual(sub.order_line[0].order_id.currency_id.id, self.company.currency_id.id, "Subscription product's order line must be created with the default company currency (USD).")
            self.assertEqual(sub.pricelist_id.id, default_pricelist.id, "Subscription must be created with the default company pricelist (in USD).")
            self.env['sale.order']._cron_recurring_create_invoice()
            self.flush_tracking()

        with freeze_time("2023-04-05"):
            action = sub.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])

            # Assert that parent_line_id is saved in renewed subscription.
            self.assertEqual(renewal_so.order_line[0].parent_line_id.id, sub.order_line[0].id, "The parent line of the order line should have been saved after subscription renewal.")
            renewal_so.pricelist_id = other_pricelist.id

            # Computes the updated price unit through 'Update Prices' button.
            renewal_so.action_update_prices()
            renewal_so.invalidate_recordset()

            # Assert that updated pricing has the correct currency, price_unit and pricelist.
            self.assertEqual(renewal_so.pricelist_id.id, other_pricelist.id, "Pricelist must update to the new one (in EUR) after performing a manual update.")
            self.assertEqual(renewal_so.order_line[0].currency_id.id, other_currency.id, "Order line's currency should have been updated from USD to EUR after changing the pricelist.")
            self.assertEqual(renewal_so.order_line[0].price_unit, 200.0, "Order line's price unit must update to 200.0 according to the new pricelist pricing (in EUR).")

            # Update prices button removes the parent_line_id of order lines to recalculate pricings.
            self.assertFalse(renewal_so.order_line[0].parent_line_id, "Parent order line should not exist anymore after updating prices, it was intentionally deleted for forcing price recalculation.")

    def test_reopen_parent_child_canceled(self):
        """ Renew a contract a few time, invoice it, check the computed amount of invoices
        Then cancel a non invoiced renewal and see if it restart the parent
        """
        with freeze_time("2023-11-03"):
            self.flush_tracking()
            self.subscription.write({
                    'start_date': False,
                    'next_invoice_date': False,
                    'partner_invoice_id': self.partner_a_invoice.id,
                    'partner_shipping_id': self.partner_a_shipping.id,
                })
            self.subscription.action_confirm()
            self.flush_tracking()
            self.subscription._create_recurring_invoice()
            self.assertEqual(self.subscription.invoice_count, 1)
            self.flush_tracking()

        with freeze_time("2023-12-03"):
            action = self.subscription.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            self.flush_tracking()
            renewal_so.action_confirm()
            self.flush_tracking()
            renewal_so._create_recurring_invoice()
            self.assertEqual(renewal_so.invoice_count, 2)
            self.flush_tracking()
        with freeze_time("2024-01-03"):
            action = renewal_so.prepare_renewal_order()
            renewal_so2 = self.env['sale.order'].browse(action['res_id'])
            self.flush_tracking()
            renewal_so2.action_confirm()
            self.flush_tracking()

            self.assertEqual(renewal_so.subscription_state, '5_renewed')
            self.assertEqual(renewal_so2.subscription_state, '3_progress')

            renewal_so2._action_cancel()
            renewal_so.end_date = False

            self.flush_tracking()
            self.assertEqual(renewal_so.subscription_state, '3_progress')
            self.assertFalse(renewal_so2.subscription_state)
        with freeze_time("2024-02-03"):
            renewal_so._create_recurring_invoice()
            self.flush_tracking()
            (self.subscription | renewal_so | renewal_so2).invalidate_recordset(['invoice_ids', 'invoice_count'])
            self.assertEqual(renewal_so.invoice_count, 3, "All contracts have the same count")
            self.assertEqual(renewal_so2.invoice_count, 3, "All contracts have the same count")
            self.assertEqual(self.subscription.invoice_count, 3, "All contracts have the same count")

    def test_renew_simple_user(self):
        user_sales_salesman = self.company_data['default_user_salesman']
        self.assertTrue(user_sales_salesman.has_group('sales_team.group_sale_salesman'))
        subscription = self.env['sale.order'].with_user(user_sales_salesman).create({
                'partner_id': self.partner_a.id,
                'company_id': self.company_data['company'].id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 2.0,
                        'price_unit': 12,
                    })],
        })
        subscription.with_user(user_sales_salesman).action_confirm()
        self.env['sale.order']._cron_recurring_create_invoice()
        action = subscription.with_user(user_sales_salesman).prepare_renewal_order()
        renewal_so = self.env['sale.order'].browse(action['res_id'])
        renewal_so.with_user(user_sales_salesman).action_confirm()

    def test_renewal_duplicate_warrning(self):
        self.subscription.write({
            'partner_id': self.user_portal.partner_id.id,
            'client_order_ref': 'co_ref'
        })
        self.subscription.action_confirm()
        self.subscription._create_recurring_invoice()
        action = self.subscription.with_context(tracking_disable=False).prepare_renewal_order()
        renewal_so = self.env['sale.order'].browse(action['res_id'])
        self.assertFalse(renewal_so.duplicated_order_ids, "Renewal qutation should not marked as duplicate order and not show warning")
