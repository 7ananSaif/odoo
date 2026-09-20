# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import freeze_time, tagged
from odoo.tools import format_date

from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('post_install', '-at_install')
class TestSubscriptionUpsell(TestSubscriptionCommon):
    def test_upsell_no_start_date(self):
        self.sub_product_tmpl.subscription_rule_ids = [(5, 0, 0)]
        self.subscription_tmpl.write({
            'sale_order_template_line_ids': [
                Command.create({
                    'name': "Optional Products",
                    'display_type': 'line_section',
                    'is_optional': True,
                }),
                Command.create({
                    'name': "Option 1",
                    'product_id': self.product5.id,
                    'product_uom_qty': 1,
                    'product_uom_id': self.product5.uom_id.id,
                })
            ]
        })
        self.subscription.write({
                'partner_id': self.partner.id,
                'plan_id': self.plan_month.id,
                'order_line': [Command.create({'product_id': self.product.id,
                                               'name': "Monthly cheap",
                                               'price_unit': 42,
                                               'product_uom_qty': 2,
                                               }),
                               Command.create({'product_id': self.product2.id,
                                               'name': "Monthly expensive",
                                               'price_unit': 420,
                                               'product_uom_qty': 3,
                                               }),
                               ]
            })
        self.subscription.action_confirm()
        self.env['sale.order']._cron_recurring_create_invoice()
        self.subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
        action = self.subscription.prepare_upsell_order()
        upsell_so = self.env['sale.order'].browse(action['res_id'])
        upsell_so.order_line.filtered(lambda l: not l.display_type).product_uom_qty = 6
        upsell_so.start_date = False
        upsell_so.action_confirm()
        upsell_so._create_invoices()
        self.assertEqual(self.subscription.order_line.sorted('id').mapped('product_uom_qty'), [7.0, 7.0, 8.0, 9.0])

    def test_upsell_via_so(self):
        # Test the upsell flow using an intermediary upsell quote.
        self.sub_product_tmpl.subscription_rule_ids = [(5, 0, 0)]
        self.subscription_tmpl.write({
            'sale_order_template_line_ids': [
                Command.create({
                    'name': "Optional Products",
                    'display_type': 'line_section',
                    'is_optional': True,
                }),
                Command.create({
                    'name': "Option 1",
                    'product_id': self.product5.id,
                    'product_uom_qty': 1,
                    'product_uom_id': self.product5.uom_id.id,
                })
            ]
        })
        self.product_tmpl_2.subscription_rule_ids = [(5, 0, 0)]
        self.env['product.pricelist.item'].create({'plan_id': self.plan_month.id, 'product_tmpl_id': self.sub_product_tmpl.id, 'fixed_price': 42})
        self.env['product.pricelist.item'].create({'plan_id': self.plan_month.id, 'product_tmpl_id': self.product_tmpl_2.id, 'fixed_price': 420})
        with freeze_time("2021-01-01"):
            self.subscription.order_line = False
            self.subscription.start_date = False
            self.subscription.next_invoice_date = False
            self.subscription.write({
                'partner_id': self.partner.id,
                'partner_invoice_id': self.partner_a_invoice.id,
                'partner_shipping_id': self.partner_a_shipping.id,
                'plan_id': self.plan_month.id,
                'order_line': [Command.create({'product_id': self.product.id,
                                               'name': "Monthly cheap",
                                               'price_unit': 42,
                                               'product_uom_qty': 2,
                                               }),
                               Command.create({'product_id': self.product2.id,
                                               'name': "Monthly expensive",
                                               'price_unit': 420,
                                               'product_uom_qty': 3,
                                               }),
                               ]
            })
            self.subscription.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()
            self.subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()

            self.assertEqual(self.subscription.order_line.sorted('id').mapped('product_uom_qty'), [2, 3], "Quantities should be equal to 2 and 3")
        with freeze_time("2021-01-15"):
            action = self.subscription.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            self.assertEqual(upsell_so.partner_invoice_id, self.partner_a_invoice)
            self.assertEqual(upsell_so.partner_shipping_id, self.partner_a_shipping)
            self.assertEqual(upsell_so.order_line.mapped('product_uom_qty'), [0, 0, 0], 'The upsell order has 0 quantity')
            note = upsell_so.order_line.filtered('display_type')
            self.assertEqual(note.name, '(*) These recurring products are discounted according to the prorated period from 01/15/2021 to 01/31/2021')
            self.assertEqual(upsell_so.order_line.product_id, self.subscription.order_line.product_id)
            upsell_so.order_line.filtered(lambda l: not l.display_type).product_uom_qty = 1
            # When the upsell order is created, all quantities are equal to 0
            # add line to quote manually, it must be taken into account in the subscription after validation
            upsell_so.order_line = [(0, 0, {
                'name': self.product2.name,
                'order_id': upsell_so.id,
                'product_id': self.product2.id,
                'product_uom_qty': 2,
                'price_unit': self.product2.list_price,
            }), (0, 0, {
                'name': self.product3.name,
                'order_id': upsell_so.id,
                'product_id': self.product3.id,
                'product_uom_qty': 1,
                'price_unit': self.product3.list_price,
            })]
            upsell_so.action_confirm()
            self.subscription._create_recurring_invoice()
            self.subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
            discounts = [round(v, 2) for v in upsell_so.order_line.sorted('discount').mapped('discount')]
            self.assertEqual(discounts, [0.0, 45.16, 45.16, 45.16, 45.16], 'Prorated prices should be applied')
            prices = [round(v, 2) for v in upsell_so.order_line.sorted('id').mapped('price_subtotal')]
            self.assertEqual(prices, [23.03, 230.33, 0, 21.94, 23.03], 'Prorated prices should be applied')

        with freeze_time("2021-02-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()

        with freeze_time("2021-03-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            upsell_so._create_invoices()
            self.subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
            sorted_lines = self.subscription.order_line.sorted('id')
            self.assertEqual(sorted_lines.mapped('product_uom_qty'), [3.0, 4.0, 2.0, 1.0], "Quantities should be equal to 3.0, 4.0, 2.0, 1.0")

        with freeze_time("2021-04-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
        with freeze_time("2021-05-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
        with freeze_time("2021-06-01"):
            self.subscription._create_recurring_invoice()
            self.subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
        with freeze_time("2021-07-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
        with freeze_time("2021-08-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
            inv = self.subscription.invoice_ids.sorted('date')[-1]
            invoice_periods = inv.invoice_line_ids.sorted('id').mapped('name')
            first_period = invoice_periods[0].split('\n')[2]
            self.assertEqual(first_period, "1 Month 08/01/2021 to 08/31/2021")
            second_period = invoice_periods[1].split('\n')[2]
            self.assertEqual(second_period, "1 Month 08/01/2021 to 08/31/2021")

        self.assertEqual(len(self.subscription.order_line), 4)

    def test_upsell_prorata(self):
        """ Test the prorated values obtained when creating an upsell. complementary to the previous one where new
         lines had no existing default values.
        """
        self.env['product.pricelist.item'].create({'plan_id': self.plan_2_month.id, 'product_tmpl_id': self.sub_product_tmpl.id, 'fixed_price': 42})
        self.env['product.pricelist.item'].create({'plan_id': self.plan_2_month.id, 'product_tmpl_id': self.product_tmpl_2.id, 'fixed_price': 42})
        with freeze_time("2021-01-01"):
            self.subscription.order_line = False
            self.subscription.start_date = False
            self.subscription.next_invoice_date = False
            self.subscription.write({
                'partner_id': self.partner.id,
                'plan_id': self.plan_2_month.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'name': "month: original",
                        'price_unit': 50,
                        'product_uom_qty': 1,
                    }),
                    Command.create({
                        'product_id': self.product2.id,
                        'name': "2 month: original",
                        'price_unit': 50,
                        'product_uom_qty': 1,
                    }),
                ]
            })

            self.subscription.action_confirm()
            self.subscription._create_recurring_invoice()

        with freeze_time("2021-01-20"):
            action = self.subscription.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            # Create new lines that should be aligned with existing ones
            so_line_vals = [{
                'name': 'Upsell added: 1 month',
                'order_id': upsell_so.id,
                'product_id': self.product2.id,
                'product_uom_qty': 1,
                'price_unit': self.product.list_price,
            }, {
                'name': 'Upsell added: 2 month',
                'order_id': upsell_so.id,
                'product_id': self.product3.id,
                'product_uom_qty': 1,
                'price_unit': self.product3.list_price,
            }]
            self.env['sale.order.line'].create(so_line_vals)
            upsell_so.order_line.product_uom_qty = 1
            discounts = [round(v) for v in upsell_so.order_line.sorted('discount').mapped('discount')]
            # discounts for: 40/59 days
            self.assertEqual(discounts, [0, 32, 32, 32, 32], 'Prorated prices should be applied')
            self.assertEqual(self.subscription.order_line.ids, upsell_so.order_line.parent_line_id.ids,
                             "The parent line id should correspond to the first two lines")
            # discounts for: 12d/31d; 40d/59d; 21d/31d (shifted); 31d/41d; 59d/78d;
            self.assertEqual(discounts, [0, 32, 32, 32, 32], 'Prorated prices should be applied')
            prices = [round(v, 2) for v in upsell_so.order_line.sorted('price_subtotal').mapped('price_subtotal')]
            self.assertEqual(prices, [0.0, 28.48, 28.48, 28.48, 28.48], 'Prorated prices should be applied')

    def test_upsell_date_check(self):
        """ Test what happens when the upsell invoice is not generated before the next invoice cron call """
        self.sub_product_tmpl.subscription_rule_ids = [
            Command.create({'plan_id': self.plan_year.id, 'fixed_price': 100}),
        ]
        self.product_tmpl_2.subscription_rule_ids = [
            Command.create({'plan_id': self.plan_year.id, 'fixed_price': 200}),
        ]
        self.product_tmpl_3.subscription_rule_ids = [
            Command.create({'plan_id': self.plan_year.id, 'fixed_price': 300}),
        ]
        with freeze_time("2022-01-01"):
            sub = self.env['sale.order'].create({
                'name': 'TestSubscription',
                'is_subscription': True,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,

                'plan_id': self.plan_year.id,
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 1.0,
                    }),
                    (0, 0, {
                        'name': self.product2.name,
                        'product_id': self.product2.id,
                        'product_uom_qty': 1.0,
                    })
                ]
            })
            sub.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()
            inv = sub.invoice_ids
            line_names = inv.invoice_line_ids.mapped('name')
            periods = [n.split('\n')[1] for n in line_names]
            for p in periods:
                self.assertEqual(p, '1 Year 01/01/2022 to 12/31/2022', 'the first year should be invoiced')

        with freeze_time("2022-06-20"):
            action = sub.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            upsell_so.order_line[0].product_uom_qty = 2
            upsell_so.order_line = [(0, 0, {
                'product_id': self.product3.id,
                'product_uom_qty': 1.0,
            })]
            self.assertEqual(upsell_so.next_invoice_date, datetime.date(2023, 1, 1), "The end date is the same than the parent sub")
            discounts = upsell_so.order_line.mapped('discount')
            self.assertEqual(discounts, [46.58, 46.58, 0.0, 46.58], "The discount is almost equal to 50%")
            self.assertEqual(sub.next_invoice_date, datetime.date(2023, 1, 1), 'the first year should be invoiced')
            upsell_so.action_confirm()
            self.assertEqual(upsell_so.next_invoice_date, datetime.date(2023, 1, 1), 'the first year should be invoiced')
            # We trigger the invoice cron before the generation of the upsell invoice
            self.env['sale.order']._cron_recurring_create_invoice()
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.date, datetime.date(2022, 1, 1), "No invoice should be created")
        with freeze_time("2022-07-01"):
            discount = upsell_so.order_line.mapped('discount')[0]
            self.assertEqual(discount, 46.58, "The discount is almost equal to 50% and should not be updated for confirmed SO")
            self.assertEqual(upsell_so.order_line.mapped('qty_to_invoice'), [2, 0, 0, 1])
            upsell_invoice = upsell_so._create_invoices()
            inv_line_ids = upsell_invoice.invoice_line_ids.filtered('product_id')
            self.assertEqual(inv_line_ids.mapped('subscription_id'), upsell_so.subscription_id)
            self.assertEqual(inv_line_ids.mapped('deferred_start_date'), [datetime.date(2022, 6, 20), datetime.date(2022, 6, 20)])
            self.assertEqual(inv_line_ids.mapped('deferred_end_date'), [datetime.date(2022, 12, 31), datetime.date(2022, 12, 31)])
            (upsell_so | sub)._cron_recurring_create_invoice()
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.date, datetime.date(2022, 1, 1), "No invoice should be created")
            self.assertEqual(upsell_invoice.amount_untaxed, 267.1, "The upsell amount should be equal to 267.1") # (1-0.4658)*(200+300)

        with freeze_time("2023-01-01"):
            (upsell_so | sub)._cron_recurring_create_invoice()
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.date, datetime.date(2023, 1, 1), "A new invoice should be created")
            self.assertEqual(inv.amount_untaxed, 800, "A new invoice should be created, all the lines should be invoiced")

        with freeze_time("2023-01-01"):
            (upsell_so | sub)._cron_recurring_create_invoice()
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.date, datetime.date(2023, 1, 1), "A new invoice should be created")
            self.assertEqual(inv.amount_untaxed, 800, "A new invoice should be created, all the lines should be invoiced")

    def test_upsell_parent_line_id(self):
        with freeze_time("2022-01-01"):
            self.subscription.order_line = False
            self.subscription.write({
                'partner_id': self.partner.id,
                'plan_id': self.plan_month.id,
                'start_date': False,
                'next_invoice_date': False,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'name': "month: original",
                        'price_unit': 50,
                        'product_uom_qty': 1,
                    })
                ]
            })
            self.subscription.action_confirm()
            self.subscription._create_recurring_invoice()

        with freeze_time("2022-01-20"):
            action = self.subscription.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            # Create new lines that should be aligned with existing ones
            parent_line_id = upsell_so.order_line.parent_line_id
            self.assertEqual(self.subscription.order_line, parent_line_id, "The parent line is the one from the subscription")
            first_line_id = upsell_so.order_line[0] # line 0 is the upsell line
            first_line_id.product_id = self.product2
            self.assertFalse(first_line_id.parent_line_id, "The new line should not have a parent line")
            upsell_so.currency_id = False
            self.assertFalse(first_line_id.parent_line_id, "The new line should not have a parent line even without currency_id")
            self.subscription._compute_pricelist_id() # reset the currency_id
            upsell_so._compute_pricelist_id()
            first_line_id.product_id = self.product
            upsell_so.order_line[0].price_unit = parent_line_id.price_unit + 0.004 # making sure that rounding issue will not affect computed result
            self.assertEqual(upsell_so.order_line[0].parent_line_id, parent_line_id, "The parent line is the one from the subscription")
            self.assertEqual(upsell_so.order_line.parent_line_id, parent_line_id,
                             "The parent line is still the one from the subscription")
            # reset the product to another one to lose the link
            first_line_id.product_id = self.product2
            so_line_vals = [{
                'name': 'Upsell added: 1 month',
                'order_id': upsell_so.id,
                'product_id': self.product3.id,
                'product_uom_qty': 3,
            }]
            self.env['sale.order.line'].create(so_line_vals)
            self.assertFalse(upsell_so.order_line[2].parent_line_id, "The new line should not have any parent line")
            upsell_so.order_line[2].product_id = self.product3
            upsell_so.order_line[2].product_id = self.product # it should recreate a link
            upsell_so.order_line[0].product_uom_qty = 2
            self.assertEqual(upsell_so.order_line.parent_line_id, parent_line_id,
                             "The parent line is the one from the subscription")
            upsell_so.action_confirm()
            self.assertEqual(self.subscription.order_line[0].product_uom_qty, 4, "The original line qty should be 4 (1 + 3 upsell line 1)")
            self.assertEqual(self.subscription.order_line[1].product_uom_qty, 2, "The new line qty should be 2 (upsell line 0)")

            action = self.subscription.prepare_renewal_order()
            renew_so = self.env['sale.order'].browse(action['res_id'])
            parent_line_id = renew_so.order_line.parent_line_id
            self.assertEqual(self.subscription.order_line, parent_line_id, "The parent line is the one from the subscription")
            renew_so.plan_id = self.plan_year
            self.assertFalse(renew_so.order_line.parent_line_id, "The lines should not have parent lines anymore")

        # test the general behavior of so when the compute_price_unit is called
        self.product_tmpl_4.recurring_invoice = False
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'sale_order_template_id': self.subscription_tmpl.id,
            'plan_id': self.plan_month.id,
            'order_line': [
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 12,
                }),
                (0, 0, {
                    'name': self.product5.name, # non recurring product
                    'product_id': self.product5.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 12,
                })
            ],
        })
        self.assertTrue(order.is_subscription)
        self.assertEqual(order.order_line[1].price_unit, 12)
        order.order_line[1].product_id = self.product_tmpl_4.product_variant_id
        self.assertEqual(order.order_line[1].price_unit, 15, "The price should be updated")

    def test_upsell_renewal(self):
        """ Upselling a invoiced renewed order before it started should create a negative discount to invoice the previous
            period. If the renewal has not been invoiced yet, we should only invoice for the previous period.
        """
        with freeze_time("2022-01-01"):
            self.subscription.start_date = False
            self.subscription.next_invoice_date = False
            self.subscription.write({
                'partner_id': self.partner.id,
                'plan_id': self.plan_year.id,
            })
            subscription_2 = self.subscription.copy()
            (self.subscription | subscription_2).action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()

        with freeze_time("2022-09-10"):
            action = self.subscription.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so.action_confirm()
            renewal_so._create_invoices()
            renewal_so.order_line.invoice_lines.move_id._post()
            self.assertEqual(renewal_so.start_date, datetime.date(2023, 1, 1))
            self.assertEqual(renewal_so.next_invoice_date, datetime.date(2024, 1, 1))
            action = subscription_2.prepare_renewal_order()
            renewal_so_2 = self.env['sale.order'].browse(action['res_id'])
            renewal_so_2.action_confirm()
            # We don't invoice renewal_so_2 yet to see what happens.
            self.assertEqual(renewal_so_2.start_date, datetime.date(2023, 1, 1))
            self.assertEqual(renewal_so_2.next_invoice_date, datetime.date(2023, 1, 1))
        with freeze_time("2022-10-02"):
            self.env['sale.order']._cron_recurring_create_invoice()
            action = renewal_so.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            upsell_so.order_line.filtered(lambda l: not l.display_type).product_uom_qty = 1
            renewal_so_2.next_invoice_date += relativedelta(days=1) # prevent validation error
            action = renewal_so_2.prepare_upsell_order()
            upsell_so_2 = self.env['sale.order'].browse(action['res_id'])
            upsell_so_2.order_line.filtered(lambda l: not l.display_type).product_uom_qty = 1
            parents = upsell_so.order_line.mapped('parent_line_id')
            line_match = [
                renewal_so.order_line[0],
                renewal_so.order_line[1],
            ]
            for idx in range(2):
                self.assertEqual(parents[idx], line_match[idx])
            self.assertEqual(self.subscription.order_line.mapped('product_uom_qty'), [1, 1])
            self.assertEqual(renewal_so.order_line.mapped('product_uom_qty'), [1, 1])
            upsell_so.action_confirm()
            self.assertEqual(upsell_so.order_line.mapped('product_uom_qty'), [1.0, 1.0, 0])
            self.assertEqual(renewal_so.order_line.mapped('product_uom_qty'), [2, 2])
            self.assertEqual(upsell_so.order_line.mapped('discount'), [-24.93, -24.93, 0])
            self.assertEqual(upsell_so.start_date, datetime.date(2022, 10, 2))
            self.assertEqual(upsell_so.next_invoice_date, datetime.date(2024, 1, 1))
            self.assertEqual(upsell_so_2.amount_untaxed, 30.25)
            # upsell_so_2.order_line.flush()
            line = upsell_so_2.order_line.filtered('display_type')
            self.assertEqual(line.display_type, 'subscription_discount')
            self.assertFalse(line.product_uom_qty)
            self.assertFalse(line.price_unit)
            self.assertFalse(line.customer_lead)
            self.assertFalse(line.product_id)

            self.assertEqual(upsell_so_2.order_line.mapped('product_uom_qty'), [1.0, 1.0, 0])
            for discount, value in zip(upsell_so_2.order_line.mapped('discount'), [74.79, 74.79, 0.0]):
                self.assertAlmostEqual(discount, value)
            self.assertEqual(upsell_so_2.next_invoice_date, datetime.date(2023, 1, 2),
                             'We only invoice until the start of the renewal')

    def test_upsell_with_different_currency_throws_error(self):
        pricelist_eur = self.env['product.pricelist'].create({
            'name': 'Euro pricelist',
            'currency_id': self.env.ref('base.EUR').id,
        })
        self.subscription.action_confirm()
        self.subscription._create_recurring_invoice()
        action = self.subscription.prepare_upsell_order()
        upsell_so = self.env['sale.order'].browse(action['res_id'])
        with self.assertRaises(ValidationError):
            upsell_so.pricelist_id = pricelist_eur.id

    def test_modify_discount_on_upsell(self):
        """
        Makes sure that you can edit the discount on an upsell, save it, and then confirm it,
        and it doesn't change/reset to default
        """
        with freeze_time("2022-10-31"):
            self.subscription.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()
            action = self.subscription.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            upsell_line = upsell_so.order_line.filtered(lambda l: not l.display_type)[0]
            old_discount = upsell_line.discount
            new_discount = 42
            self.assertTrue(old_discount != new_discount,
                            "These discounts should be different, change the value of new_discount if this test fail.")
            upsell_line.write({'discount': new_discount})
            self.assertEqual(upsell_line.discount, new_discount,
                             "The line should have the new discount written.")
            upsell_so.action_confirm()
            self.assertEqual(upsell_line.discount, new_discount,
                             "The line should have the new discount after confirmation.")

    def test_upsell_total_qty(self):
        self.subscription.action_confirm()
        self.subscription._create_recurring_invoice()
        next_invoice_date = self.subscription.next_invoice_date
        action = self.subscription.prepare_upsell_order()
        upsell_so = self.env['sale.order'].browse(action['res_id'])
        upsell_so.order_line.filtered(lambda l: not l.display_type).product_uom_qty = 2
        upsell_so.action_confirm()
        for line in upsell_so.order_line.filtered(lambda l: not l.display_type):
            self.assertEqual(line.upsell_total, 3)
        invoice = upsell_so._create_invoices()
        # simulate wrong historical data
        invoice.invoice_line_ids.filtered('deferred_end_date').deferred_end_date = next_invoice_date + relativedelta(days=5)
        invoice._post()
        self.assertEqual(self.subscription.next_invoice_date, next_invoice_date, "The next Invoice date should not be updated by an upsell")

    def test_sale_subscription_upsell_does_not_copy_non_recurring_products(self):
        nr_product = self.env['product.template'].create({
            'name': 'Non recurring product',
            'type': 'service',
            'uom_id': self.product.uom_id.id,
            'list_price': 25,
            'invoice_policy': 'order',
        })
        self.subscription.action_confirm()
        self.subscription._create_recurring_invoice()

        action = self.subscription.prepare_upsell_order()
        upsell_so = self.env['sale.order'].browse(action['res_id'])
        upsell_so.order_line = [(6, 0, self.env['sale.order.line'].create({
            'name': nr_product.name,
            'order_id': upsell_so.id,
            'product_id': nr_product.product_variant_id.id,
            'product_uom_qty': 1,
        }).ids)]

        upsell_so._confirm_upsell()
        self.assertEqual(len(upsell_so.order_line), 1)
        self.assertEqual(len(self.subscription.order_line), 2)
        self.assertEqual(upsell_so.order_line.name, nr_product.name)
        self.assertFalse(nr_product in self.subscription.order_line.product_template_id)

    def test_upsell_descriptions(self):
        """ On invoicing upsells, only subscription-based items should display a duration. """
        with freeze_time("2022-10-31"):
            self.subscription.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()

            action = self.subscription.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            upsell_so.order_line = [Command.create({'product_id': self.product_a.id})]
            upsell_so.order_line.filtered('product_id').product_uom_qty = 1
            upsell_so.action_confirm()
            invoice = upsell_so._create_invoices()

            self.assertEqual(len(invoice.invoice_line_ids), 4)
            for line in invoice.invoice_line_ids:
                name = line.name
                sol_name = line.sale_line_ids.name
                if line.sale_line_ids.recurring_invoice:
                    self.assertIn("1 Month", name, "Sub lines require duration")
                else:
                    self.assertEqual(name, sol_name, "Non-sub lines shouldn't add duration")

    def test_upsell_line_note_update(self):
        """"
        Test that the line note is handled correctly in upsell orders:
        For positive discount upsell orders, the line note remains unchanged.
        For negative discount upsell orders, the line note is updated to reflect the surcharged prorated period.
        """
        with freeze_time("2022-01-01"):
            self.subscription.write({
                'partner_id': self.partner.id,
                'plan_id': self.plan_year.id,
                'name': 'First order'
            })
            # Test the positive discount (line note remains unchanged)
            # Create a second sale order (for positive discount scenario)
            sale_order_2 = self.subscription.copy({'name': 'Second order'})
            (self.subscription | sale_order_2).action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()

        with freeze_time("2022-09-10"):
            action = sale_order_2.prepare_upsell_order()
            upsell_so_2 = self.env['sale.order'].browse(action['res_id'])
            upsell_so_2.name = "Upsell of second order"
            upsell_so_2.order_line.filtered(lambda l: not l.display_type).product_uom_qty = 1
            self.assertEqual(upsell_so_2.order_line.mapped('product_uom_qty'), [1.0, 1.0, 0])
            upsell_so_2.action_confirm()

            self.assertEqual(upsell_so_2.order_line.mapped('discount'), [69.04, 69.04, 0])
            expected_line_name = (
                '(*) These recurring products are discounted according to the prorated period from %s to %s' % (
                format_date(self.env, upsell_so_2.start_date),
                format_date(self.env, upsell_so_2.next_invoice_date - relativedelta(days=1))
            ))
            upsell_order_line_note = upsell_so_2.order_line.filtered(lambda l: l.display_type == 'subscription_discount').name
            self.assertEqual(expected_line_name, upsell_order_line_note)

            # Test for negative discount (line note should be updated)
            # Prepare and confirm the renewal order (for negative discount scenario)
            action = self.subscription.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so.name = 'Renewal SO'
            renewal_so.action_confirm()
            renewal_so._create_invoices()
            renewal_so.order_line.invoice_lines.move_id._post()

            self.assertEqual(renewal_so.start_date, datetime.date(2023, 1, 1))
            self.assertEqual(renewal_so.next_invoice_date, datetime.date(2024, 1, 1))

        with freeze_time("2022-10-02"):
            self.env['sale.order']._cron_recurring_create_invoice()
            action = renewal_so.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            upsell_so.name = "Upsell of renewal"
            upsell_so.order_line.filtered(lambda l: not l.display_type).product_uom_qty = 1
            upsell_so.action_confirm()

            # Assert that the discounts are negative and the line note is updated accordingly
            self.assertEqual(upsell_so.order_line.mapped('discount'), [-24.93, -24.93, 0])
            expected_line_name = (
                '(*) These recurring products are surcharged according to the prorated period from %s to %s' % (
                format_date(self.env, upsell_so.start_date),
                format_date(self.env, upsell_so.next_invoice_date - relativedelta(days=1))
            ))
            upsell_order_line_note = upsell_so.order_line.filtered(lambda l: l.display_type == 'subscription_discount').name
            self.assertEqual(expected_line_name, upsell_order_line_note)

    def test_copy_follower_on_upsell_or_renew_order_from_parent(self):
        """
        Test that followers from parent sale order are getting copied to the renew or upsell order.
        """
        with freeze_time("2024-11-01"):
            self.subscription.action_confirm()
            self.subscription.message_subscribe(partner_ids=self.sale_user.partner_id.ids)
            self.env['sale.order']._cron_recurring_create_invoice()

        with freeze_time("2024-11-10"):
            action = self.subscription.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so.action_confirm()
            renewal_so._create_invoices()
            renewal_so.order_line.invoice_lines.move_id._post()
            self.assertIn(
                self.sale_user.partner_id, renewal_so.message_partner_ids,
                "Parent order's followers should be copied into renew order.")
            # add a new follower in the renew order
            renewal_so.message_subscribe(partner_ids=(self.partner + self.legit_user.partner_id).ids)

            # create a upsell order from renewal order
            action = renewal_so.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            self.assertEqual(
                upsell_so.message_partner_ids, (self.sale_user + self.env.user).partner_id,
                "Parent order's internal followers should be copied into upsell order, not customers")
