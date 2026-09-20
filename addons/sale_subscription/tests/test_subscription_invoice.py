# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged, freeze_time
from odoo.tools import mute_logger
from odoo.exceptions import AccessError, UserError

from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon, UncatchableException


@tagged('post_install', '-at_install')
class TestSubscriptionInvoice(TestSubscriptionCommon):
    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_automatic(self):
        self.assertTrue(True)
        sub = self.subscription
        context_no_mail = {'no_reset_password': True, 'mail_create_nosubscribe': True, 'mail_create_nolog': True, }
        sub_product_tmpl = self.env['product.template'].with_context(context_no_mail).create({
            'name': 'Subscription Product',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'list_price': 42
        })
        product = sub_product_tmpl.product_variant_id
        template = self.env['sale.order.template'].create({
            'name': 'Subscription template without discount',
            'duration_unit': 'year',
            'is_unlimited': False,
            'duration_value': 2,
            'plan_id': self.plan_month.id,
            'sale_order_template_line_ids': [Command.create({
                'name': "monthly",
                'product_id': product.id,
                'product_uom_id': product.uom_id.id
            }),
                Command.create({
                    'name': "yearly",
                    'product_id': product.id,
                    'product_uom_id': product.uom_id.id,
                })
            ]

        })
        self.plan_month.auto_close_limit = 3
        self.company = self.env.company

        self.provider = self.env['payment.provider'].create(
            {'name': 'The Wire',
             'company_id': self.company.id,
             'state': 'test',
             'redirect_form_view_id': self.env['ir.ui.view'].search([('type', '=', 'qweb')], limit=1).id})

        sub.sale_order_template_id = template.id
        sub._onchange_sale_order_template_id()
        with freeze_time("2021-01-03"):
            sub.write({'start_date': False, 'next_invoice_date': False})
            sub.action_confirm()
            self.assertEqual(sub.invoice_count, 0)
            self.assertEqual(datetime.date(2021, 1, 3), sub.start_date, 'start date should be reset at confirmation')
            self.assertEqual(datetime.date(2021, 1, 3), sub.next_invoice_date, 'next invoice date should be updated')
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(datetime.date(2021, 2, 3), sub.next_invoice_date, 'next invoice date should be updated')
            inv = sub.invoice_ids.sorted('date')[-1]
            inv_line = inv.invoice_line_ids[0].sorted('id')[0]
            invoice_periods = inv_line.name.split('\n')[2]
            self.assertEqual(invoice_periods, "1 Month 01/03/2021 to 02/02/2021")
            self.assertEqual(inv_line.date, datetime.date(2021, 1, 3))

        with freeze_time("2021-02-03"):
            self.assertEqual(sub.invoice_count, 1)
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(sub.invoice_count, 2)
            self.assertEqual(datetime.date(2021, 1, 3), sub.start_date, 'start date should not changed')
            self.assertEqual(datetime.date(2021, 3, 3), sub.next_invoice_date, 'next invoice date should be in 1 month')
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_periods = inv.invoice_line_ids[1].name.split('\n')[2]
            self.assertEqual(invoice_periods, "1 Month 02/03/2021 to 03/02/2021")
            self.assertEqual(inv.invoice_line_ids[1].date, datetime.date(2021, 2, 3))

        with freeze_time("2021-03-03"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(datetime.date(2021, 4, 3), sub.next_invoice_date, 'next invoice date should be in 1 month')
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_periods = inv.invoice_line_ids[0].name.split('\n')[2]
            self.assertEqual(invoice_periods, "1 Month 03/03/2021 to 04/02/2021")
            self.assertEqual(inv.invoice_line_ids[0].date, datetime.date(2021, 3, 3))

    def test_invoicing_with_section(self):
        """ Test invoicing when order has section/note."""

        # create specific test products
        sub_product1_tmpl = self.env['product.template'].with_context(self.context_no_mail).create({
            'name': 'Subscription #A',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        sub_product1 = sub_product1_tmpl.product_variant_id
        sub_product2_tmpl = self.env['product.template'].with_context(self.context_no_mail).create({
            'name': 'Subscription #B',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        sub_product2 = sub_product2_tmpl.product_variant_id
        sub_product_onetime_discount_tmpl = self.env['product.template'].with_context(self.context_no_mail).create({
            'name': 'Initial discount',
            'type': 'service',
            'recurring_invoice': False,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        sub_product_onetime_discount = sub_product_onetime_discount_tmpl.product_variant_id

        with freeze_time("2021-01-03"):
            sub = self.env["sale.order"].with_context(**self.context_no_mail).create({
                'name': 'TestSubscription',
                'is_subscription': True,
                'plan_id': self.plan_month.id,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'sale_order_template_id': self.subscription_tmpl.id,
            })
            sub._onchange_sale_order_template_id()
            sub.write({
                'start_date': False,
                'end_date': False,
                'next_invoice_date': False,
            })
            sub.order_line = [
                Command.clear(),
                Command.create({
                    'display_type': 'line_section',
                    'name': 'Products',
                }),
                Command.create({
                    'product_id': sub_product1.id,
                    'name': "Subscription #A",
                    'price_unit': 42,
                    'product_uom_qty': 2,
                }),
                Command.create({
                    'product_id': sub_product2.id,
                    'name': "Subscription #B",
                    'price_unit': 42,
                    'product_uom_qty': 2,
                }),
                Command.create({
                    'product_id': sub_product_onetime_discount.id,
                    'name': 'Initial discount New subscription discount (one-time)',
                    'price_unit': -10.0,
                    'product_uom_qty': 2,
                }),
                Command.create({
                    'display_type': 'line_section',
                    'name': 'Information',
                }),
                Command.create({
                    'display_type': 'line_note',
                    'name': '...',
                }),
            ]
            sub.action_confirm()
            sub._create_invoices()

        # first invoice, it should include one-time discount
        self.assertEqual(len(sub.invoice_ids), 1)
        sub.invoice_ids._post()
        invoice = sub.invoice_ids[-1]
        self.assertEqual(invoice.amount_untaxed, 148.0)
        self.assertEqual(len(invoice.invoice_line_ids), 4)
        self.assertRecordValues(invoice.invoice_line_ids, [
            {'display_type': 'line_section', 'name': 'Products', 'product_id': False},
            {
                'display_type': 'product', 'product_id': sub_product1.id,
                'name': 'Subscription #A\n1 Month 01/03/2021 to 02/02/2021',
            },
            {
                'display_type': 'product', 'product_id': sub_product2.id,
                'name': 'Subscription #B\n1 Month 01/03/2021 to 02/02/2021',
            },
            {
                'display_type': 'product', 'product_id': sub_product_onetime_discount.id,
                'name': 'Initial discount New subscription discount (one-time)',
            },
        ])

        with freeze_time("2021-02-03"):
            invoice = sub._create_invoices()
            invoice._post()

        # second invoice, should NOT include one-time discount
        self.assertEqual(len(sub.invoice_ids), 2)
        self.assertEqual(invoice.amount_untaxed, 168.0)
        self.assertEqual(len(invoice.invoice_line_ids), 3)
        self.assertRecordValues(invoice.invoice_line_ids, [
            {'display_type': 'line_section', 'name': 'Products', 'product_id': False},
            {
                'display_type': 'product', 'product_id': sub_product1.id,
                'name': 'Subscription #A\n1 Month 02/03/2021 to 03/02/2021',
            },
            {
                'display_type': 'product', 'product_id': sub_product2.id,
                'name': 'Subscription #B\n1 Month 02/03/2021 to 03/02/2021',
            },
        ])

    def test_add_aml_to_invoice(self):
        """ Test that it is possible to manually add a line with a start and end
        date to an invoice generated from a subscription sale order.
        """
        sub_product1, sub_product2 = self.env['product.product'].create([
            {
                'name': 'SubA',
                'type': 'service',
                'recurring_invoice': True,
                'invoice_policy': 'order',
            },
            {
                'name': 'SubB',
                'type': 'service',
                'recurring_invoice': True,
            }
        ])

        sub = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'partner_id': self.user_portal.partner_id.id,
            'order_line': [(0, 0, {'product_id': sub_product1.id})],
        })

        sub.action_confirm()
        invoice = sub._create_invoices()
        invoice.write({
            'line_ids': [(0, 0, {
                'product_id': sub_product2.id,
                'deferred_start_date': '2015-03-14',
                'deferred_end_date': '2030-06-28',
            })],
        })
        invoice._post()  # should not throw an error
        self.assertEqual(invoice.line_ids.product_id, sub_product1 | sub_product2)

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_unlimited_sale_order(self):
        """ Test behaviour of on_change_template """
        with freeze_time("2021-01-03"):
            sub = self.subscription
            sub.order_line = [Command.clear()]
            context_no_mail = {'no_reset_password': True, 'mail_create_nosubscribe': True, 'mail_create_nolog': True, }
            sub_product_tmpl = self.env['product.template'].with_context(context_no_mail).create({
                'name': 'Subscription Product',
                'type': 'service',
                'recurring_invoice': True,
                'uom_id': self.env.ref('uom.product_uom_unit').id,
            })
            product = sub_product_tmpl.product_variant_id
            sub.order_line = [Command.create({'product_id': product.id,
                                              'name': "coucou",
                                              'price_unit': 42,
                                              'product_uom_qty': 2,
                                              })]
            sub.write({'start_date': False, 'next_invoice_date': False})
            sub.action_confirm()
            self.assertFalse(sub.last_invoice_date)
            self.assertEqual("2021-01-03", sub.start_date.strftime("%Y-%m-%d"))
            self.assertEqual("2021-01-03", sub.next_invoice_date.strftime("%Y-%m-%d"))

            sub._create_recurring_invoice()
            # Next invoice date should not be bumped up because it is the first period
            self.assertEqual("2021-02-03", sub.next_invoice_date.strftime("%Y-%m-%d"))

            invoice_periods = sub.invoice_ids.invoice_line_ids.name.split('\n')[2]
            self.assertEqual(invoice_periods, "1 Month 01/03/2021 to 02/02/2021")
            self.assertEqual(sub.invoice_ids.invoice_line_ids.date, datetime.date(2021, 1, 3))
        with freeze_time("2021-02-03"):
            # February
            sub._create_recurring_invoice()
            self.assertEqual("2021-02-03", sub.last_invoice_date.strftime("%Y-%m-%d"))
            self.assertEqual("2021-03-03", sub.next_invoice_date.strftime("%Y-%m-%d"))
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_periods = inv.invoice_line_ids.name.split('\n')[2]
            self.assertEqual(invoice_periods, "1 Month 02/03/2021 to 03/02/2021")
            self.assertEqual(inv.invoice_line_ids.date, datetime.date(2021, 2, 3))
        with freeze_time("2021-03-03"):
            # March
            sub._create_recurring_invoice()
            self.assertEqual("2021-03-03", sub.last_invoice_date.strftime("%Y-%m-%d"))
            self.assertEqual("2021-04-03", sub.next_invoice_date.strftime("%Y-%m-%d"))
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_periods = inv.invoice_line_ids.name.split('\n')[2]
            self.assertEqual(invoice_periods, "1 Month 03/03/2021 to 04/02/2021")
            self.assertEqual(inv.invoice_line_ids.date, datetime.date(2021, 3, 3))

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_invoice_on_period_start_service_sale_order(self):
        """ Test behaviour of on_change_template """
        with freeze_time("2021-01-15"):
            sub = self.subscription
            sub.order_line = [Command.clear()]
            sub_product_tmpl = self.ProductTmpl.create({
                'name': 'Subscription Product',
                'type': 'service',
                'recurring_invoice': True,
                'uom_id': self.env.ref('uom.product_uom_unit').id,
            })
            product = sub_product_tmpl.product_variant_id
            sub.order_line = [Command.create({'product_id': product.id,
                                              'name': "coucou",
                                              'price_unit': 42,
                                              'product_uom_qty': 2,
                                              })]
            sub.write({'start_date': False, 'next_invoice_date': False, 'end_date': '2021-03-18'})
            sub.plan_id.billing_first_day = True
            sub.action_confirm()
            inv = sub._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 84 * 17 / 31, 1, msg="15 to 31 is 17 days (15 and 31 included)")

        with freeze_time("2021-02-01"):
            # February
            inv = sub._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 84)

        with freeze_time("2021-03-01"):
            # March
            inv = sub._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 84, 1, msg="Last period is full too 01 to 01 even if the end_date occurs in the middle of the period")

    def test_quantity_on_product_invoice_ordered_qty(self):
        # This test checks that the invoiced qty and to_invoice qty have the right behavior
        # Service product
        self.product.write({
            'type': 'service'
        })
        with freeze_time("2021-01-01"):
            self.subscription.order_line = False
            self.subscription.write({
                'start_date': False,
                'next_invoice_date': False,
                'plan_id': self.plan_month.id,
                'partner_id': self.partner.id,
                'order_line': [Command.create({'product_id': self.product2.id,
                                               'price_unit': 420,
                                               'product_uom_qty': 3,
                                               }),
                                Command.create({'product_id': self.product.id,
                                               'price_unit': 42,
                                               'product_uom_qty': 1,
                                               }),
                               ]
            })
            self.subscription.action_confirm()
            val_confirm = self._get_quantities(self.subscription.order_line)
            self.assertEqual(val_confirm['to_invoice'], [3, 1], "To invoice should be equal to quantity")
            self.assertEqual(val_confirm['invoiced'], [0, 0], "To invoice should be equal to quantity")
            self.assertEqual(val_confirm['delivered'], [0, 0], "Delivered qty not should be set")
            self.env['sale.order']._cron_recurring_create_invoice()
            self.subscription.order_line[0].write({'qty_delivered': 3})
            self.subscription.order_line[1].write({'qty_delivered': 1})
            val_invoice = self._get_quantities(self.subscription.order_line)
            self.assertEqual(val_invoice['invoiced'], [3, 1], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['to_invoice'], [0, 0], "To invoice should be 0")
            self.assertEqual(val_invoice['delivered'], [3, 1], "Delivered qty should be set")

        with freeze_time("2021-01-05"):
            val_invoice = self._get_quantities(self.subscription.order_line)
            self.assertEqual(val_invoice['invoiced'], [3, 1], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['to_invoice'], [0, 0], "To invoice should be 0")
            self.assertEqual(val_invoice['delivered'], [3, 1], "Delivered qty should be set")

        with freeze_time("2021-02-02"):
            self.env['sale.order']._cron_recurring_create_invoice()
            val_invoice = self._get_quantities(self.subscription.order_line)
            self.assertEqual(val_invoice['to_invoice'], [0, 0], "To invoice should be 0")
            self.assertEqual(val_invoice['invoiced'], [3, 1], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['delivered'], [3, 1], "Delivered qty should be equal to quantity")

        with freeze_time("2021-02-15"):
            self.subscription.order_line[1].write({'qty_delivered': 3, 'product_uom_qty': 3})
            val_invoice = self._get_quantities(
                self.subscription.order_line
            )
            self.assertEqual(val_invoice['to_invoice'], [0, 2], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['invoiced'], [3, 1], "invoiced should be correct")
            self.assertEqual(val_invoice['delivered'], [3, 3], "Delivered qty should be equal to quantity")

        with freeze_time("2021-03-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.env.invalidate_all()
            val_invoice = self._get_quantities(self.subscription.order_line)
            self.assertEqual(val_invoice['to_invoice'], [0, 0], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['delivered'], [3, 3], "Delivered qty should be equal to quantity")
            self.assertEqual(val_invoice['invoiced'], [3, 3], "To invoice should be equal to quantity delivered")

    def test_product_invoice_delivery(self):
        sub = self.subscription
        sub.order_line = [Command.clear()]
        delivered_product_tmpl = self.env['product.template'].with_context(self.context_no_mail).create({
            'name': 'Delivery product',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'invoice_policy': 'delivery',
        })
        product = delivered_product_tmpl.product_variant_id
        product.write({
            'list_price': 50.0,
            'taxes_id': [(6, 0, [self.tax_10.id])],
            'property_account_income_id': self.account_income.id,
        })

        with freeze_time("2021-01-03"):
            # January
            sub.plan_id = self.plan_month
            sub.start_date = False
            sub.next_invoice_date = False
            sub.order_line = [Command.create({'product_id': product.id,
                                              'name': "coucou",
                                              'price_unit': 42,
                                              'product_uom_qty': 1,
                                              })]
            sub.action_confirm()
            sub._create_recurring_invoice()
            self.assertFalse(sub.order_line.qty_delivered)
            # We only invoice what we deliver
            self.assertFalse(sub.order_line.qty_to_invoice)
            self.assertFalse(sub.invoice_count, "We don't invoice if we don't deliver the product")
            self.assertEqual(sub.next_invoice_date, datetime.date(2021, 2, 3), 'But we still update the next invoice date')

        with freeze_time("2021-02-03"):
            # Deliver some product
            sub.order_line.qty_delivered = 1
            self.assertEqual(sub.order_line.qty_to_invoice, 1)
            inv = sub._create_recurring_invoice()
            self.assertEqual(inv.invoice_line_ids.deferred_start_date, datetime.date(2021, 1, 3))
            self.assertEqual(inv.invoice_line_ids.deferred_end_date, datetime.date(2021, 2, 2))
            self.assertTrue(sub.invoice_count, "We should have invoiced")
            self.assertEqual(sub.next_invoice_date, datetime.date(2021, 3, 3))

        with freeze_time("2021-03-03"):
            inv = sub._create_recurring_invoice()
            # The quantity to invoice and delivered are reset after the creation of the invoice
            self.assertTrue(sub.order_line.qty_delivered)
            self.assertEqual(inv.invoice_line_ids.quantity, 1)

        with freeze_time("2021-04-03"):
            # February
            sub.order_line.qty_delivered = 1
            sub._create_recurring_invoice()
            self.assertEqual(sub.order_line.qty_delivered, 1)
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.invoice_line_ids.quantity, 1)

        with freeze_time("2021-05-03"):
            # March
            sub.order_line.qty_delivered = 2
            sub._create_recurring_invoice()
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.invoice_line_ids.quantity, 2)
            self.assertEqual(sub.order_line.product_uom_qty, 1)

        with freeze_time("2021-04-03"):
            # February
            sub.order_line.qty_delivered = 1
            sub._create_recurring_invoice()
            self.assertEqual(sub.order_line.qty_delivered, 1)
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.invoice_line_ids.quantity, 2)

        with freeze_time("2021-05-03"):
            # March
            sub.order_line.qty_delivered = 2
            sub._create_recurring_invoice()
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.invoice_line_ids.quantity, 2)
            self.assertEqual(sub.order_line.product_uom_qty, 1)

    def test_recurring_invoices_from_interface(self):
        # From the interface, all the subscription lines are invoiced
        sub = self.subscription
        sub.end_date = datetime.date(2029, 4, 1)
        with freeze_time("2021-01-01"):
            self.subscription.write({'start_date': False, 'next_invoice_date': False, 'plan_id': self.plan_month.id})
            sub.action_confirm()
            # first invoice: automatic or not, it's the same behavior. All line are invoiced
            sub._create_invoices()
            sub.order_line.invoice_lines.move_id._post()
            self.assertEqual("2021-02-01", sub.next_invoice_date.strftime("%Y-%m-%d"))
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_start_periods = inv.invoice_line_ids.mapped('deferred_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('deferred_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 1, 1), datetime.date(2021, 1, 1)])
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 1, 31), datetime.date(2021, 1, 31)])
        with freeze_time("2021-02-01"):
            sub._create_invoices()
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_start_periods = inv.invoice_line_ids.mapped('deferred_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('deferred_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 2, 1), datetime.date(2021, 2, 1)], "monthly is updated everytime in manual action")
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 2, 28), datetime.date(2021, 2, 28)], "both lines are invoiced")
            with self.assertRaisesRegex(UserError, 'The following recurring orders have draft invoices. Please Confirm them or cancel them'):
                sub._create_invoices()
            inv._post()
            self.assertEqual("2021-03-01", sub.next_invoice_date.strftime("%Y-%m-%d"), "Next invoice date should be updated")
            sub._create_invoices()
            inv = sub.invoice_ids.sorted('id')[-1]
            inv._post()
            self.assertEqual("2021-04-01", sub.next_invoice_date.strftime("%Y-%m-%d"))
            invoice_start_periods = inv.invoice_line_ids.mapped('deferred_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('deferred_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 3, 1), datetime.date(2021, 3, 1)], "monthly is updated everytime in manual action")
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 3, 31), datetime.date(2021, 3, 31)], "monthly is updated everytime in manual action")

        with freeze_time("2021-04-01"):
            # Automatic invoicing, only one line generated
            inv = sub._create_recurring_invoice()
            invoice_start_periods = inv.invoice_line_ids.mapped('deferred_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('deferred_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 4, 1), datetime.date(2021, 4, 1)], "Monthly is updated because it is due")
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 4, 30), datetime.date(2021, 4, 30)], "Monthly is updated because it is due")
            self.assertEqual(inv.date, datetime.date(2021, 4, 1))

        with freeze_time("2021-05-01"):
            # Automatic invoicing, only one line generated
            sub._create_recurring_invoice()
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_start_periods = inv.invoice_line_ids.mapped('deferred_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('deferred_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 5, 1), datetime.date(2021, 5, 1)], "Monthly is updated because it is due")
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 5, 31), datetime.date(2021, 5, 31)], "Monthly is updated because it is due")
            self.assertEqual(inv.date, datetime.date(2021, 5, 1))

        with freeze_time("2022-02-02"):
            # We prevent the subscription to be automatically closed because the next invoice date is passed for too long
            sub.plan_id.auto_close_limit = 999
            # With non-automatic, we invoice all line prior to today once
            inv = sub._create_invoices()
            inv._post()
            self.assertEqual("2021-07-01", sub.next_invoice_date.strftime("%Y-%m-%d"), "on the 1st of may, nid is updated to 1fst of june and here we force the line to be apdated again")
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_start_periods = inv.invoice_line_ids.mapped('deferred_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('deferred_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 6, 1), datetime.date(2021, 6, 1)], "monthly is updated when prior to today")
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 6, 30), datetime.date(2021, 6, 30)], "monthly is updated when prior to today")

    def test_invoice_status_postpaid(self):
        with freeze_time("2022-05-15"):
            self.product.invoice_policy = 'delivery'
            subscription_future = self.env['sale.order'].create({
                'name': "subscription future",
                'partner_id': self.partner.id,
                'sale_order_template_id': self.subscription_tmpl.id,
                'plan_id': self.plan_month.id,
                'start_date': '2022-06-01',
                'next_invoice_date': '2022-06-01',
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 1.0,
                        'price_unit': 12,
                    })],
            })

            subscription_now = self.env['sale.order'].create({
                'name': "subscription now",
                'partner_id': self.partner.id,
                'sale_order_template_id': self.subscription_tmpl.id,
                'plan_id': self.plan_month.id,
                'start_date': '2022-05-15',
                'next_invoice_date': '2022-05-15',
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 1.0,
                        'price_unit': 12,
                    })],
            })

            subscription_past = subscription_now.copy({
                    'name': "subscription past",
                    'start_date': '2022-04-15',
                    'next_invoice_date': '2022-04-15',
            })

            subscriptions = subscription_future + subscription_now + subscription_past
            subscriptions.action_confirm()

            self.assertEqual(subscription_now.next_invoice_date, datetime.date(2022, 6, 15), "Postpaid subscription first invoice should be end of period")
            self.assertEqual(subscription_past.next_invoice_date, datetime.date(2022, 5, 15), "Postpaid subscription first invoice should be end of period")
            self.assertEqual(subscription_future.next_invoice_date, datetime.date(2022, 7, 1), "Postpaid subscription first invoice should be end of period")

            # Nothing delivered, nothing invoiced
            self.assertEqual(subscription_future.order_line.invoice_status, 'no', "The line qty should be black.")
            self.assertEqual(subscription_now.order_line.invoice_status, 'no', "The line qty should be black.")
            subscription_now.order_line.qty_delivered = 1
            self.assertEqual(subscription_now.order_line.invoice_status, 'to invoice', "The line qty should be blue.")

            # Status after delivery
            subscriptions.order_line.qty_delivered = 1
            self.assertEqual(
                subscription_future.order_line.invoice_status, 'no',
                "Nothing to invoice for future subscription yet.",
            )
            for subscription in (subscription_now, subscription_past):
                self.assertEqual(
                    subscription.order_line.invoice_status, 'to invoice',
                    "The line qty should be blue.",
            )
            subscriptions._create_recurring_invoice()
            self.assertEqual(subscription_past.order_line.invoice_status, 'invoiced', "The line qty should be invoiced.")
            self.assertEqual(subscription_now.order_line.invoice_status, 'to invoice', "The line qty should not be invoiced yet.")
            self.assertEqual(subscription_future.order_line.invoice_status, 'no', "The line qty should be black.")

        with freeze_time('2022-06-15'):
            subscriptions._create_recurring_invoice()
            self.assertEqual(subscription_past.order_line.invoice_status, 'invoiced', "The line qty should be invoiced.")
            self.assertEqual(subscription_now.order_line.invoice_status, 'invoiced', "The line qty should not be invoiced yet.")
            self.assertEqual(subscription_future.order_line.invoice_status, 'no', "The line qty should be black.")

    def test_refund_qty_invoiced(self):
        with freeze_time("2024-09-01"):
            subscription = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 3.0,
                        'price_unit': 12,
                    })],
            })
            subscription.action_confirm()
            subscription._create_recurring_invoice()
            self.assertEqual(subscription.order_line.qty_invoiced, 3, "The 3 products should be invoiced")
            subscription._get_invoiced()
            inv = subscription.invoice_ids
            inv.payment_state = 'paid'
            # We refund the invoice
            refund_wizard = self.env['account.move.reversal'].with_context(
                active_model="account.move",
                active_ids=inv.ids).create({
                'reason': 'Test refund tax repartition',
                'journal_id': inv.journal_id.id,
            })
            res = refund_wizard.refund_moves()
            refund_move = self.env['account.move'].browse(res['res_id'])
            self.assertEqual(inv.reversal_move_ids, refund_move, "The initial move should be reversed")
            refund_move._post()
        self.assertEqual(subscription.order_line.qty_invoiced, 0, "The products should not be invoiced")

    def test_free_product_do_not_invoice(self):
        sub_product_tmpl = self.env['product.template'].create({
            'name': 'Free product',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'list_price': 0,
        })

        self.subscription.start_date = False
        self.subscription.next_invoice_date = False
        self.subscription.order_line = [Command.clear()]
        self.subscription.write({
            'partner_id': self.partner.id,
            'plan_id': self.plan_year.id,
            'order_line': [Command.create({
                'name': sub_product_tmpl.name,
                'product_id': sub_product_tmpl.product_variant_id.id,
                'product_uom_qty': 1.0,
            })]
        })
        self.assertEqual(self.subscription.amount_untaxed, 0, "The price shot be 0")
        self.assertEqual(self.subscription.order_line.price_subtotal, 0, "The price line should be 0")
        self.assertEqual(self.subscription.order_line.invoice_status, 'no', "Nothing to invoice here")

    def test_invoice_done_order(self):
        # Prevent to invoice order in subscription_state != 3_progress
        with freeze_time("2021-01-03"):
            self.subscription.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(self.subscription.invoice_count, 1, "one invoice is created normally")

        with freeze_time("2021-02-03"):
            action = self.subscription.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so.action_confirm()
            self.assertTrue(self.subscription.locked)
            self.env['sale.order']._cron_recurring_create_invoice()
            self.subscription._cron_recurring_create_invoice()
            self.assertEqual(self.subscription.invoice_count, 2, "locked state don't prevent invoices anymore")

    def test_downpayment_automatic_invoice(self):
        """ Test invoice with a way of downpayment and check downpayment's SO line is created
            and also check a total amount of invoice is equal to a respective sale order's total amount
        """

        context = {
            'active_model': 'sale.order',
            'active_ids': [self.subscription.id],
            'active_id': self.subscription.id,
            'default_journal_id': self.company_data['default_journal_sale'].id,
        }

        with freeze_time('2021-01-03'):
            self.subscription.action_confirm()
            total = self.subscription.amount_total

            downpayment = self.env['sale.advance.payment.inv'].with_context(context).create({
                'advance_payment_method': 'fixed',
                'fixed_amount': 10,
            })
            downpayment.create_invoices()
            downpayment_line = self.subscription.order_line.filtered(lambda l: l.is_downpayment and not l.display_type)
            self.assertEqual(len(downpayment_line), 1, 'SO line downpayment should be created on SO')

            self.assertEqual(self.subscription.invoice_count, 1)
            invoice = self.subscription.invoice_ids.sorted('id')[-1]
            self.assertAlmostEqual(invoice.amount_total, 10, 4, msg='Downpayment price should be 10')
            invoice._post()
            self.assertEqual(self.subscription.next_invoice_date, datetime.date(2021, 1, 3))
            invoice = self.subscription._create_invoices(final=True)  # manual
            self.assertAlmostEqual(invoice.amount_total, total - 10, 4, msg='Downpayment should be deducted from the price')
            invoice._post()
            self.assertEqual(self.subscription.next_invoice_date, datetime.date(2021, 2, 3))

        with freeze_time('2021-02-03'):
            inv = self.subscription._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_total, total, 4, msg='Downpayment should not be deducted from the price anymore')

    def test_downpayment_manual_invoice(self):
        """ Test invoice with a way of downpayment and check downpayment's SO line is created
            and also check a total amount of invoice is equal to a respective sale order's total amount
        """

        context = {
            'active_model': 'sale.order',
            'active_ids': [self.subscription.id],
            'active_id': self.subscription.id,
            'default_journal_id': self.company_data['default_journal_sale'].id,
        }

        with freeze_time('2021-01-03'):
            self.subscription.action_confirm()
            total = self.subscription.amount_total
            self.assertEqual(total, 23.1)
            downpayment = self.env['sale.advance.payment.inv'].with_context(context).create({
                'advance_payment_method': 'fixed',
                'fixed_amount': 10,
            })
            downpayment.create_invoices()
            downpayment_line = self.subscription.order_line.filtered(lambda l: l.is_downpayment and not l.display_type)
            self.assertEqual(len(downpayment_line), 1, 'SO line downpayment should be created on SO')

            self.assertEqual(self.subscription.invoice_count, 1)
            invoice = self.subscription.invoice_ids.sorted('id')[-1]
            self.assertAlmostEqual(invoice.amount_total, 10, 4, msg='Downpayment price should be 10')
            invoice._post()

            invoice = self.subscription._create_invoices(final=True)
            invoice._post()

            self.assertAlmostEqual(invoice.amount_total, total - 10, 4, msg='Downpayment should be deducted from the price')

        with freeze_time('2021-02-03'):
            invoice = self.subscription._create_invoices(final=True)
            self.assertAlmostEqual(invoice.amount_total, total, 4,
                                   msg='Downpayment should not be deducted from the price anymore')

    def test_sale_subscription_post_invoice(self):
        """ Test that the post invoice hook is correctly called
        """
        def patched_reset(self):
            self.name = "Called"

        with patch('odoo.addons.sale_subscription.models.sale_order_line.SaleOrderLine._reset_subscription_quantity_post_invoice', patched_reset), freeze_time("2021-01-01"):
            sub = self.subscription
            sub.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(sub.order_line.mapped('name'), ['Called'] * 2)

    def test_qty_invoiced_after_revert(self):
        """ Test invoice quantity is correctly updated after a revert
            with modify move creation
        """
        self.subscription.write({
            'order_line': [
                Command.clear(),
                Command.create({
                    'name': self.product.name,
                    'product_id': self.product.id,
                    'product_uom_qty': 2.0,
                    'price_unit': 12,
                })],
        })
        self.subscription.action_confirm()
        self.env['sale.order']._cron_recurring_create_invoice()
        invoice = self.subscription.invoice_ids
        move_reversal = self.env['account.move.reversal'].with_context(active_model="account.move", active_ids=invoice.ids).create({
            'reason': 'no reason',
            'journal_id': invoice.journal_id.id,
        })
        reversal = move_reversal.modify_moves()
        new_move = self.env['account.move'].browse(reversal['res_id'])
        new_move.action_post()
        self.assertEqual(self.subscription.order_line.qty_invoiced, 2.0, "Invoiced quantity on the order line is not correct")

    def test_recurring_invoice_count(self):
        sub = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'partner_id': self.user_portal.partner_id.id,
            'order_line': [(0, 0, {'product_id': self.product.id})],
        })
        sub.action_confirm()
        inv = self.env['sale.order']._cron_recurring_create_invoice()
        new_invoice = inv.copy()
        self.assertEqual(sub.invoice_ids, inv | new_invoice)

    def test_invoicing_access_rights(self):
        """Ensure a salesman can get amount invoiced for subscriptions with others' invoices."""
        sales_user = self.company_data['default_user_salesman']
        self.product_a.write({
            'name': "Non-recurring product",
            'recurring_invoice': False,
        })
        self.subscription.write({
            'user_id': sales_user.id,
            'order_line': [Command.create({
                'product_id': self.product_a.id,
                'tax_ids': False,
            })],
        })
        self.subscription.action_confirm()
        self.assertAlmostEqual(
            self.subscription.with_user(sales_user).amount_to_invoice,
            sum(self.subscription.order_line.mapped('price_total')),
            msg="All lines should still need to be invoiced",
        )

        # assign a different user to the invoice
        invoice = self.subscription._create_recurring_invoice()
        invoice.user_id = self.env.ref('base.user_admin')

        # ensure salesman doesn't have access to just any invoice
        invoice.invalidate_recordset(['name'])
        with self.assertRaises(AccessError):
            invoice.with_user(sales_user).user_id = sales_user

        self.assertAlmostEqual(
            self.subscription.with_user(sales_user).amount_invoiced,
            self.product_a.list_price,
            msg="We should get the amount invoiced for non-recurring products",
        )

    @freeze_time("2025-04-14")
    def test_failing_sub_invoice_flag(self):
        """ Make sure that when the cron is crashing, we don't end up with successful subscription with an error flag.
        Processed subscriptions are
        """
        self.subscription.write({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'payment_token_id': self.payment_token.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        self.subscription._onchange_sale_order_template_id()
        self.subscription.action_confirm()
        start_date = datetime.date.today()
        self.subscription.start_date = start_date
        self.subscription.payment_token_id = False
        subs = self.env['sale.order']
        for _i in range(3):
            subs |= self.subscription.copy()
        # last sub of the batch will make the cron crash.
        # _create_recurring_invoice revert the order of subscriptions and we want to crash on the last one
        self.crashing_sub_id = subs[0].id
        subs.action_confirm()
        self.assertEqual(subs.mapped('next_invoice_date'), [datetime.date(2025, 4, 14), datetime.date(2025, 4, 14), datetime.date(2025, 4, 14)])
        # Create invoices, the third should crash but only the last one will keep is_invoice_cron value
        try:
            with patch(
                    'odoo.addons.sale_subscription.models.sale_order.SaleOrder._process_invoices_to_send',
                    wraps=self._mock_subscription_process_invoice_to_send
            ), mute_logger('odoo.addons.sale_subscription.models.sale_order'):
                subs._create_recurring_invoice()
        except UncatchableException:
            pass
        self.assertEqual(subs.mapped('is_invoice_cron'), [True, False, False])
        invs = self.env['account.move'].search([('invoice_line_ids.subscription_id', 'in', subs.ids)])
        self.assertEqual(invs.mapped('state'), ["posted", "posted", "posted"])
        # Make sure next time it's running it reset all is_invoice_cron
        self.env['sale.order']._create_recurring_invoice()
        self.assertEqual(subs.mapped('is_invoice_cron'), [False, False, False])

    def test_invoice_delivery_free(self):
        # Ensure free subscription are not processed endlessly by cron
        with freeze_time('2025-11-11'):
            sub = self.subscription
            sub.order_line[0].unlink()
            sub.order_line.product_id.invoice_policy = "delivery"
            # ensure at confirmation the next invoice date will be today
            sub.start_date = datetime.date.today() - datetime.timedelta(days=31)
            sub.action_confirm()
            self.assertEqual(sub.next_invoice_date, datetime.date(2025, 11, 11))
            self.assertFalse(sub.order_line.qty_delivered, "We don't deliver the product for the first period")
            sub._create_recurring_invoice()
            self.assertEqual(sub.next_invoice_date, datetime.date(2025, 12, 11))
        with freeze_time('2025-12-11'):
            sub._create_recurring_invoice()
            self.assertEqual(sub.next_invoice_date, datetime.date(2026, 1, 11))
            self.assertFalse(sub.invoice_ids, "No invoice should be created")
