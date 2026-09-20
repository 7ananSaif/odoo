import datetime

from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, freeze_time, tagged
from odoo.tools import mute_logger

from odoo.addons.account_accountant.tests.test_signature import TestInvoiceSignature
from odoo.addons.mail.tests.common import MockEmail
from odoo.addons.sale_subscription.models.sale_order import SaleOrder
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('post_install', '-at_install')
class TestSubscription(TestSubscriptionCommon, MockEmail):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_a.recurring_invoice = False

    @classmethod
    def default_env_context(cls):
        return {}

    def setUp(self):
        super(TestSubscription, self).setUp()
        self.other_currency = self.setup_other_currency('CAD')
        self.env.ref('base.group_user').write({"implied_ids": [(4, self.env.ref('sale_management.group_sale_order_template').id)]})
        self.flush_tracking()

        self.post_process_patcher = patch(
            'odoo.addons.account_payment.models.payment_transaction.PaymentTransaction._post_process',
        )
        self.startPatcher(self.post_process_patcher)

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_template(self):
        """ Test behaviour of on_change_template """
        Subscription = self.env['sale.order']
        self.assertEqual(self.subscription.note, Markup('<p>original subscription description</p>'), "Original subscription note")
        # on_change_template on cached record (NOT present in the db)
        temp = Subscription.new({'name': 'CachedSubscription',
                                 'partner_id': self.user_portal.partner_id.id})
        temp.update({'sale_order_template_id': self.subscription_tmpl.id})
        temp._onchange_sale_order_template_id()
        self.assertEqual(temp.note, Markup('<p>This is the template description</p>'), 'Override the subscription note')

    def test_template_without_selected_partner(self):
        """ Create a subscription by choosing a template before the customer """
        with Form(self.env['sale.order']) as subscription:
            subscription.sale_order_template_id = self.subscription_tmpl
            subscription.partner_id = self.partner # mandatory to have no error

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_limited_service_sale_order(self):
        """ Test behaviour of on_change_template """
        with freeze_time("2021-01-03"):
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
            sub.action_confirm()
            inv = sub._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 84)

        with freeze_time("2021-02-03"):
            # February
            inv = sub._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 84)

        with freeze_time("2021-03-03"):
            # March
            inv = sub._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 84, 1,  msg="Last period is full too 01 to 01 even if the end_date occurs in the middle of the period")

    def test_sale_subscription_set_date(self):
        """ Test case to verify that updating the `start_date` on a copied upsell sale order
            correctly sets the new date in the subscription. """
        with freeze_time("2024-11-01"):
            self.subscription.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()

        with freeze_time("2024-11-11"):
            # Prepare the upsell order from the subscription
            action = self.subscription.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            # Copy the upsell order
            upsell_so_new = upsell_so.copy()
            # Set a new start date on the copied upsell order
            new_start_date = fields.Date.from_string("2024-11-12")
            upsell_so_new.write({'start_date': new_start_date})
            self.assertEqual(upsell_so_new.start_date, new_start_date, "The start date of the copied upsell order should be updated.")

    def test_subscription_order_line_description(self):
        with freeze_time("2024-04-01"):
            self.subscription.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()

        with freeze_time("2024-04-15"):
            action = self.subscription.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            self.assertEqual(upsell_so.order_line.mapped('discount'), [46.67, 46.67, 0])
            self.assertEqual(upsell_so.order_line[0].name, "Product 1(*)", "(*) should be added in discounted product's description")
            self.assertEqual(upsell_so.order_line[1].name, "Product 2(*)", "(*) should be added in discounted product's description")
            self.assertEqual(upsell_so.order_line[2].name, "(*) These recurring products are discounted according to the prorated period from 04/15/2024 to 04/30/2024")

    def test_recurring_revenue(self):
        """Test computation of recurring revenue"""
        # Initial subscription is $100/y
        self.subscription_tmpl.write({'duration_value': 1, 'duration_unit': 'year'})
        self.subscription.write({
            'plan_id': self.plan_2_month.id,
            'start_date': False,
            'next_invoice_date': False,
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'payment_token_id': self.payment_token.id,
        })
        self.subscription.order_line[0].write({'price_unit': 1200, 'technical_price_unit': 1200})
        self.subscription.order_line[1].write({'price_unit': 200, 'technical_price_unit': 200})
        self.subscription.action_confirm()
        self.assertAlmostEqual(self.subscription.amount_untaxed, 1400, msg="unexpected price after setup")
        self.assertAlmostEqual(self.subscription.recurring_monthly, 700, msg="Half because invoice every two months")
        # Change periodicity
        self.subscription.order_line.product_id.subscription_rule_ids = [(6, 0, 0)]  # remove all pricings to fallback on list price
        self.subscription.plan_id = self.plan_year
        self.assertAlmostEqual(self.subscription.amount_untaxed, 70, msg='Recompute price_unit : 50 (product) + 20 (product2)')
        # 1200 over 4 year = 25/year + 100 per month
        self.assertAlmostEqual(self.subscription.recurring_monthly, 5.84, msg='70 / 12')

    def test_recurring_total(self):
        """Test rounding of (non-) recurring total"""
        self.company.write({
            'currency_id': self.env.ref('base.BGN').id,
            'account_price_include': 'tax_included',
            'tax_calculation_rounding_method': 'round_globally',
        })
        sub_tax = self.env['account.tax'].create({
            'name': '20% BG',
            'amount': 20,
            'company_id': self.company.id,
        })
        subscription = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'company_id': self.company.id,
            'plan_id': self.plan_month.id,
            'partner_id': self.user_portal.partner_id.id,
            'order_line': [
                Command.create({'product_id': self.product.id,
                                'price_unit': 140,
                                'tax_ids': [Command.set(sub_tax.ids)]
                                }),
                Command.create({'product_id': self.product.id,
                                'price_unit': 36.97,
                                'tax_ids': [Command.set(sub_tax.ids)]
                                }),
                Command.create({'product_id': self.product.id,
                                'price_unit': 36.97,
                                'tax_ids': [Command.set(sub_tax.ids)]
                                }),
                Command.create({'product_id': self.product.id,
                                'price_unit': 21,
                                'tax_ids': [Command.set(sub_tax.ids)]
                                }),
                ]
        })
        self.assertEqual(subscription.non_recurring_total, 0)
        self.assertEqual(subscription.recurring_total, 195.78)

    def test_compute_kpi(self):
        self.subscription.action_confirm()
        self.env['sale.order']._cron_update_kpi()

        # 16 to 6 weeks: 80
        # 6 to 2 weeks: 100
        # 2weeks - today : 120
        date_log = datetime.date.today() - relativedelta(weeks=16)
        self.env['sale.order.log'].sudo().create({
            'event_type': '1_expansion',
            'event_date': date_log,
            'create_date': date_log,
            'order_id': self.subscription.id,
            'recurring_monthly': 80,
            'amount_signed': 80,
            'currency_id': self.subscription.currency_id.id,
            'subscription_state': self.subscription.subscription_state,
            'user_id': self.subscription.user_id.id,
            'team_id': self.subscription.team_id.id,
        })

        date_log = datetime.date.today() - relativedelta(weeks=6)
        self.env['sale.order.log'].sudo().create({
            'event_type': '1_expansion',
            'event_date': date_log,
            'create_date': date_log,
            'order_id': self.subscription.id,
            'recurring_monthly': 100,
            'amount_signed': 20,
            'currency_id': self.subscription.currency_id.id,
            'subscription_state': self.subscription.subscription_state,
            'user_id': self.subscription.user_id.id,
            'team_id': self.subscription.team_id.id,
         })

        self.subscription.recurring_monthly = 120.0
        date_log = datetime.date.today() - relativedelta(weeks=2)
        self.env['sale.order.log'].sudo().create({
            'event_type': '1_expansion',
            'event_date': date_log,
            'create_date': date_log,
            'order_id': self.subscription.id,
            'recurring_monthly': 120,
            'amount_signed': 20,
            'currency_id': self.subscription.currency_id.id,
            'subscription_state': self.subscription.subscription_state,
            'user_id': self.subscription.user_id.id,
            'team_id': self.subscription.team_id.id,
        })
        self.subscription._cron_update_kpi()
        self.assertEqual(self.subscription.kpi_1month_mrr_delta, 20.0)
        self.assertEqual(self.subscription.kpi_1month_mrr_percentage, 0.2)
        self.assertEqual(self.subscription.kpi_3months_mrr_delta, 40.0)
        self.assertEqual(self.subscription.kpi_3months_mrr_percentage, 0.5)

    def test_onchange_date_start(self):
        recurring_bound_tmpl = self.env['sale.order.template'].create({
            'name': 'Recurring Bound Template',
            'plan_id': self.plan_month.id,
            'is_unlimited': False,
            'duration_unit': 'month',
            'duration_value': 3,
            'sale_order_template_line_ids': [Command.create({
                'name': "monthly",
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'product_uom_id': self.product.uom_id.id
            })]
        })
        sub_form = Form(self.env['sale.order'])
        sub_form.partner_id = self.user_portal.partner_id
        sub_form.sale_order_template_id = recurring_bound_tmpl
        sub = sub_form.save()
        sub._onchange_sale_order_template_id()
        # The end date is set upon confirmation
        sub.action_confirm()
        self.assertEqual(sub.sale_order_template_id.is_unlimited, False)
        self.assertIsInstance(sub.end_date, datetime.date)

    def test_changed_next_invoice_date(self):
        # Test wizard to change next_invoice_date manually
        with freeze_time("2022-01-01"):
            self.subscription.write({'start_date': False, 'next_invoice_date': False})
            self.env['sale.order.line'].create({
                'name': self.product2.name,
                'order_id': self.subscription.id,
                'product_id': self.product2.id,
                'product_uom_qty': 3,
                'price_unit': 42})

            self.subscription.action_confirm()
            self.subscription._create_recurring_invoice()
            today = fields.Date.today()
            self.assertEqual(self.subscription.start_date, today, "start date should be set to today")
            self.assertEqual(self.subscription.next_invoice_date, datetime.date(2022, 2, 1))
            # We decide to invoice the monthly subscription on the 5 of february
            self.subscription.next_invoice_date = fields.Date.from_string('2022-02-05')
            # check the invoice state
            self.assertEqual(self.subscription.invoice_status, 'invoiced')

        with freeze_time("2022-02-01"):
            # Nothing should be invoiced
            self.subscription._cron_recurring_create_invoice()
            # next_invoice_date : 2022-02-05 but the previous invoice deferred_end_date was set on the 2022-02-01
            # We can't prevent it to be re-invoiced.
            inv = self.subscription.invoice_ids.sorted('date')
            # Nothing was invoiced
            self.assertEqual(inv.date, datetime.date(2022, 1, 1))

        with freeze_time("2022-02-05"):
            self.subscription._cron_recurring_create_invoice()
            inv = self.subscription.invoice_ids.sorted('date')
            self.assertEqual(inv[-1].date, datetime.date(2022, 2, 5))
            self.assertEqual(self.subscription.invoice_status, 'invoiced')

    def test_product_change(self):
        """Check behaviour of the product onchange (taxes mostly)."""
        # check default tax
        self.sub_product_tmpl.subscription_rule_ids = [
            Command.clear(),
            Command.create({'plan_id': self.plan_month.id, 'fixed_price': 50})
        ]

        self.subscription.order_line.unlink()
        sub_form = Form(self.subscription)
        sub_form.plan_id = self.plan_month
        with sub_form.order_line.new() as line:
            line.product_id = self.product
        sub = sub_form.save()
        self.assertEqual(sub.order_line.tax_ids, self.tax_10, 'Default tax for product should have been applied.')
        self.assertEqual(sub.amount_tax, 5.0,
                         'Default tax for product should have been applied.')
        self.assertEqual(sub.amount_total, 55.0,
                         'Default tax for product should have been applied.')
        # Change the product
        line_id = sub.order_line.ids
        sub.write({
            'order_line': [(1, line_id[0], {'product_id': self.product4.id})]
        })
        self.assertEqual(sub.order_line.tax_ids, self.tax_20,
                         'Default tax for product should have been applied.')
        self.assertEqual(sub.amount_tax, 3,
                         'Default tax for product should have been applied.')
        self.assertEqual(sub.amount_total, 18,
                         'Default tax for product should have been applied.')

    def test_log_change_pricing(self):
        """ Test subscription log generation when template_id is changed """
        self.sub_product_tmpl.subscription_rule_ids.fixed_price = 120  # 120 for monthly and yearly
        # Create a subscription and add a line, should have logs with MMR 120
        subscription = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'start_date': False,
            'next_invoice_date': False,
            'plan_id': self.plan_month.id,
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
            'order_line': [
                Command.create({
                    'name': 'TestRecurringLine',
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                })
            ]
        })
        self.assertEqual(
            subscription.order_line.pricelist_item_id,
            self.product.subscription_rule_ids.filtered(
                lambda rule: rule.plan_id == self.plan_month,
            )
        )
        self.assertEqual(
            subscription.order_line.price_unit,
            120
        )
        self.cr.precommit.clear()
        subscription.action_confirm()
        self.flush_tracking()
        init_nb_log = len(subscription.order_log_ids)
        self.assertEqual(subscription.order_line.recurring_monthly, 120)
        subscription.plan_id = self.plan_year
        self.assertEqual(subscription.order_line.recurring_monthly, 10)
        self.flush_tracking()
        # Should get one more log with MRR 10 (so change is -110)
        self.assertEqual(len(subscription.order_log_ids), init_nb_log + 1,
                         "Subscription log not generated after change of the subscription template")
        self.assertRecordValues(subscription.order_log_ids[-1],
                                [{'recurring_monthly': 10.0, 'amount_signed': -110}])

    def test_fiscal_position(self):
        # Test that the fiscal postion FP is applied on recurring invoice.
        # FP must mapped an included tax of 21% to an excluded one of 0%
        fp = self.env['account.fiscal.position'].create({'name': "fiscal position",
                                                         'sequence': 1,
                                                         'auto_apply': True,
                                                        })
        tax_include_id = self.env['account.tax'].create({'name': "Include tax",
                                                         'amount': 21.0,
                                                         'price_include_override': 'tax_included',
                                                         'type_tax_use': 'sale'})
        tax_exclude_id = self.env['account.tax'].create({'name': "Exclude tax",
                                                         'fiscal_position_ids': fp.ids,
                                                         'original_tax_ids': tax_include_id,
                                                         'amount': 0.0,
                                                         'type_tax_use': 'sale'})

        product_tmpl = self.env['product.template'].create(dict(name="Voiture",
                                                                list_price=121,
                                                                taxes_id=[(6, 0, [tax_include_id.id])]))

        self.subscription.fiscal_position_id = fp.id
        self.subscription.partner_id.property_account_position_id = fp
        sale_order = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'fiscal_position_id': fp.id,
            'partner_id': self.user_portal.partner_id.id,
            'order_line': [Command.create({
                'product_id': product_tmpl.product_variant_id.id,
                'product_uom_qty': 1
            })]
        })
        sale_order.action_confirm()
        inv = sale_order._create_invoices()
        self.assertEqual(100, inv.invoice_line_ids[0].price_unit, "The included tax must be subtracted to the price")

    def test_update_prices_template(self):
        recurring_bound_tmpl = self.env['sale.order.template'].create({
            'name': 'Subscription template without discount',
            'duration_unit': 'year',
            'is_unlimited': False,
            'duration_value': 2,
            'plan_id': self.plan_month.id,
            'note': "This is the template description",
            'sale_order_template_line_ids': [
                Command.create({
                    'name': "monthly",
                    'product_id': self.product.id,
                    'product_uom_id': self.product.uom_id.id
                }),
                Command.create({
                    'name': "yearly",
                    'product_id': self.product.id,
                    'product_uom_id': self.product.uom_id.id,
                }),
                Command.create({
                    'name': "Optional Products",
                    'display_type': 'line_section',
                    'is_optional': True,
                }),
                Command.create({
                    'name': "option",
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'product_uom_id': self.product2.uom_id.id,
                }),
            ],
        })

        sub_form = Form(self.env['sale.order'])
        sub_form.partner_id = self.user_portal.partner_id
        sub_form.sale_order_template_id = recurring_bound_tmpl
        sub = sub_form.save()
        self.assertEqual(len(sub.order_line.ids), 4)

    def test_mixed_delivered_ordered_products(self):
        self.product.name = "ordered Product"
        self.assertEqual(self.product.invoice_policy, 'order')
        self.assertEqual(self.product.type, 'service')
        sub = self.subscription
        sub.order_line = [Command.clear()]
        delivered_product_tmpl = self.ProductTmpl.create({
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
            sub.plan_id = self.plan_month.id
            sub.start_date = False
            sub.next_invoice_date = False
            sub.order_line = [Command.create({
                'product_id': product.id,
                'name': "delivered product",
                'price_unit': 10,
                'product_uom_qty': 1,
            }), Command.create({
                'product_id': self.product.id,
                'name': "ordered product",
                'price_unit': 5,
                'product_uom_qty': 1,
            })]
            sub.action_confirm()
            inv = sub._create_recurring_invoice()
            # We only invoice what we deliver
            self.assertEqual(sub.order_line.mapped('qty_invoiced'), [0, 1])
            self.assertEqual(sub.order_line.mapped('qty_to_invoice'), [0, 0])
            self.assertEqual(sub.order_line.mapped('qty_delivered'), [0, 0])
            self.assertEqual(sub.invoice_count, 1, "First invoice is created")
            self.assertEqual(sub.next_invoice_date, datetime.date(2021, 2, 3))

        with freeze_time("2021-02-03"):
            # Deliver some product
            sub.order_line[0].qty_delivered = 1
            inv = sub._create_recurring_invoice()
            self.assertEqual(inv.invoice_line_ids.mapped('deferred_start_date'), [datetime.date(2021, 1, 3), datetime.date(2021, 2, 3)])
            self.assertEqual(inv.invoice_line_ids.mapped('deferred_end_date'), [datetime.date(2021, 2, 2), datetime.date(2021, 3, 2)])
            self.assertTrue(sub.invoice_count, "We should have invoiced")
            self.assertEqual(sub.next_invoice_date, datetime.date(2021, 3, 3))

        with freeze_time("2021-02-15"):
            action = sub.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            self.assertEqual(upsell_so.order_line.product_id, self.product,
                         "deliver product should not be included in the upsell")

    def test_option_template(self):
        self.product.product_tmpl_id.subscription_rule_ids = [
            Command.clear(),
            Command.create({
                'fixed_price': 10,
                'plan_id': self.plan_year.id,
            }),
        ]
        other_pricelist = self.env['product.pricelist'].create({
            'name': 'New pricelist',
            'currency_id': self.company.currency_id.id,
            'item_ids': [
                Command.create({
                    'plan_id': self.plan_year.id,
                    'fixed_price': 15,
                    'product_tmpl_id': self.product.product_tmpl_id.id
                }),
            ],
        })
        template = self.env['sale.order.template'].create({
            'name': 'Subscription template without discount',
            'is_unlimited': True,
            'note': "This is the template description",
            'plan_id': self.plan_year.id,
            'sale_order_template_line_ids': [
                Command.create({
                    'name': "monthly",
                    'product_id': self.product.id,
                }),
                Command.create({
                    'name': "Optional Products",
                    'display_type': 'line_section',
                    'is_optional': True,
                }),
                Command.create({
                    'name': "line 1",
                    'product_id': self.product.id,
                }),
            ],
        })
        subscription = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': template.id,
        })
        subscription._onchange_sale_order_template_id()
        optional_lines = self._get_optional_product_lines(subscription)
        self.assertEqual(subscription.order_line[0].price_unit, 10, "The second pricing should be applied")
        self.assertEqual(optional_lines.price_unit, 10, "The second pricing should be applied")

        subscription.pricelist_id = other_pricelist.id

        subscription._onchange_sale_order_template_id()
        optional_lines = self._get_optional_product_lines(subscription)
        self.assertEqual(subscription.pricelist_id.id, other_pricelist.id, "The second pricelist should be applied")
        self.assertEqual(subscription.order_line[0].price_unit, 15, "The second pricing should be applied")
        self.assertEqual(optional_lines.price_unit, 15, "The second pricing should be applied")
        # Note: the pricing_id on the line is not saved on the line, but it is used to calculate the price.

    def test_update_subscription_company(self):
        """ Update the taxes of confirmed lines when the subscription company is updated """
        tax_group_1 = self.env['account.tax.group'].create({
            'name': 'Test tax group',
            'tax_receivable_account_id': self.company_data['default_tax_account_receivable'].copy().id,
            'tax_payable_account_id': self.company_data['default_tax_account_payable'].copy().id,
        })
        sale_tax_percentage_incl_1 = self.env['account.tax'].create({
            'name': 'sale_tax_percentage_incl_1',
            'amount': 20.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
            'tax_group_id': tax_group_1.id,
        })
        other_company_data = self.setup_other_company(name="Company 3")
        tax_group_2 = self.env['account.tax.group'].create({
            'name': 'Test tax group',
            'company_id': other_company_data['company'].id,
            'tax_receivable_account_id': other_company_data['default_tax_account_receivable'].copy().id,
            'tax_payable_account_id': other_company_data['default_tax_account_payable'].copy().id,
        })
        sale_tax_percentage_incl_2 = self.env['account.tax'].create({
            'name': 'sale_tax_percentage_incl_2',
            'amount': 40.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
            'tax_group_id': tax_group_2.id,
            'company_id': other_company_data['company'].id,
        })
        self.product.write({
            'taxes_id': [(6, 0, [sale_tax_percentage_incl_1.id, sale_tax_percentage_incl_2.id])],
        })
        simple_product = self.product.copy({'recurring_invoice': False})
        simple_so = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'company_id': self.company_data['company'].id,
            'order_line': [
                (0, 0, {
                    'name': self.product.name,
                    'product_id': simple_product.id,
                    'product_uom_qty': 2.0,
                    'price_unit': 12,
                })],
        })
        self.assertEqual(simple_so.order_line.tax_ids.id, sale_tax_percentage_incl_1.id, 'The so has the first tax')
        subscription = self.env['sale.order'].create({
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
        self.assertEqual(subscription.order_line.tax_ids.id, sale_tax_percentage_incl_1.id)
        (simple_so | subscription).write({'company_id': other_company_data['company'].id})
        self.assertEqual(simple_so.order_line.tax_ids.id, sale_tax_percentage_incl_2.id, "Simple SO taxes must be recomputed on company change")
        self.assertEqual(subscription.order_line.tax_ids.id, sale_tax_percentage_incl_2.id, "Subscription taxes must be recomputed on company change")

    def test_archive_partner_invoice_shipping(self):
        # archived a partner must not remain set on invoicing/shipping address in subscription
        # here, they are set manually on subscription
        self.subscription.action_confirm()
        self.subscription.write({
            'partner_invoice_id': self.partner_a_invoice.id,
            'partner_shipping_id': self.partner_a_shipping.id,
        })
        self.assertEqual(self.partner_a_invoice, self.subscription.partner_invoice_id,
                         "Invoice address should have been set manually on the subscription.")
        self.assertEqual(self.partner_a_shipping, self.subscription.partner_shipping_id,
                         "Delivery address should have been set manually on the subscription.")
        invoice = self.subscription._create_recurring_invoice()
        self.assertEqual(self.partner_a_invoice, invoice.partner_id,
                         "On the invoice, invoice address should be the same as on the subscription.")
        self.assertEqual(self.partner_a_shipping, invoice.partner_shipping_id,
                         "On the invoice, delivery address should be the same as on the subscription.")
        with self.assertRaises(ValidationError):
            self.partner_a.child_ids.write({'active': False})

    def test_subscription_invoice_shipping_address(self):
        """Test to check that subscription invoice first try to use partner_shipping_id and partner_id from
        subscription"""
        partner = self.env['res.partner'].create(
            {'name': 'Stevie Nicks',
             'email': 'sti@fleetwood.mac',
             'company_id': self.env.company.id})

        partner2 = self.env['res.partner'].create(
            {'name': 'Partner 2',
             'email': 'sti@fleetwood.mac',
             'company_id': self.env.company.id})

        subscription = self.env['sale.order'].create({
            'partner_id': partner.id,
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
        subscription.action_confirm()

        invoice_id = subscription._create_recurring_invoice()
        addr = subscription.partner_id.address_get(['delivery', 'invoice'])
        self.assertEqual(invoice_id.partner_shipping_id.id, addr['invoice'])
        self.assertEqual(invoice_id.partner_id.id, addr['delivery'])

        subscription.write({
            'partner_id': partner.id,
            'partner_shipping_id': partner2.id,
        })
        invoice_id = subscription._create_invoices() # force a new invoice with all lines
        self.assertEqual(invoice_id.partner_shipping_id.id, partner2.id)
        self.assertEqual(invoice_id.partner_id.id, partner.id)

    def test_subscription_starts_in_future(self):
        """ Start a subscription in 2 weeks. The next invoice date should be aligned with start_date """
        with freeze_time("2022-05-15"):
            subscription = self.env['sale.order'].create({
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
            subscription.action_confirm()
            self.assertEqual(subscription.order_line.invoice_status, 'no', "The line qty should be black.")
            self.assertEqual(subscription.start_date, datetime.date(2022, 6, 1), 'Start date should be in the future')
            self.assertEqual(subscription.next_invoice_date, datetime.date(2022, 6, 1), 'next_invoice_date should be in the future')
            subscription._create_invoices()
            with self.assertRaisesRegex(UserError, 'The following recurring orders have draft invoices. Please Confirm them or cancel them'):
                subscription._create_invoices()
            subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
            self.assertEqual(subscription.next_invoice_date, datetime.date(2022, 7, 1),
                             'next_invoice_date should updated')
            subscription._create_invoices()
            subscription.invoice_ids.filtered(lambda am: am.state == 'draft')._post()
            self.assertEqual(subscription.next_invoice_date, datetime.date(2022, 8, 1),
                             'next_invoice_date should updated')

    def test_subscription_constraint(self):
        sub = self.subscription.copy()
        self.subscription.plan_id = False
        with self.assertRaisesRegex(UserError, 'Please add a recurring plan on the subscription or remove the recurring product.'):
            self.subscription.action_confirm()
        self.subscription.plan_id = self.plan_month
        self.product.recurring_invoice = False
        self.product2.recurring_invoice = False
        with self.assertRaisesRegex(UserError, 'Please add a recurring product in the subscription or remove the recurring plan.'):
            sub2 = self.subscription.copy()
            sub2.action_confirm()
        # order linked to subscription with recurring product and no recurrence: it was created before the upgrade
        # of sale.subscription into sale.order
        delivered_product_tmpl = self.ProductTmpl.create({
            'name': 'Delivery product',
            'type': 'service',
            'recurring_invoice': False,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'invoice_policy': 'delivery',
        })
        self.product.recurring_invoice = True
        self.product2.recurring_invoice = True
        sub.action_confirm()

        # Simulate the order without recurrence but linked to a subscription
        order = self.env['sale.order'].create({
            'partner_id': self.user_portal.partner_id.id,
            'subscription_id': sub.id,
            'order_line': [Command.create({
                'name': "recurring line",
                'product_id': self.product.id,
                'product_uom_qty': 1,
                }), Command.create({
                'name': "None recurring line",
                'product_id': delivered_product_tmpl.product_variant_id.id,
                'product_uom_qty': 1,
                }),
            ],
        })
        # Make sure the _constraint_subscription_recurrence is not triggered
        self.assertFalse(order.subscription_state)
        order.action_confirm()
        order.write({'order_line': [Command.create({
                    'name': "None recurring line",
                    'product_id': delivered_product_tmpl.product_variant_id.id,
                    'product_uom_qty': 1,
                    'qty_delivered': 3,
        })],})

    def test_next_invoice_date(self):
        with freeze_time("2022-01-20"):
            subscription = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'sale_order_template_id': self.subscription_tmpl.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 1.0,
                        'price_unit': 12,
                    })],
            })
            self.assertFalse(subscription.next_invoice_date)
            self.assertFalse(subscription.start_date)

        with freeze_time("2022-02-10"):
            subscription.action_confirm()
            self.assertEqual(subscription.next_invoice_date, datetime.date(2022, 2, 10))
            self.assertEqual(subscription.start_date, datetime.date(2022, 2, 10))

    def test_discount_parent_line(self):
        with freeze_time("2022-01-01"):
            self.subscription.start_date = False
            self.subscription.next_invoice_date = False
            self.subscription.write({
                'partner_id': self.partner.id,
                'plan_id': self.plan_year.id,
            })
            self.subscription.order_line.discount = 10
            self.subscription.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()
        with freeze_time("2022-10-31"):
            self.env['sale.order']._cron_recurring_create_invoice()
            action = self.subscription.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            # Discount is 55.61: 83% for pro rata temporis and 10% coming from the parent order
            # price_unit must be multiplied by (1-0.831) * 0,9
            # 100 * [1 - ((1 - 0.831) * 0.9)] = ~84%
            discount = [round(v, 2) for v in upsell_so.order_line.mapped('discount')]
            self.assertEqual(discount, [84.71, 84.71, 0])

    def test_create_alternative(self):
        self.subscription.next_invoice_date = fields.Date.today() + relativedelta(months=1)
        action = self.subscription.prepare_renewal_order()
        renewal_so = self.env['sale.order'].browse(action['res_id'])
        copy_so = renewal_so.copy()
        alternative_action = renewal_so.create_alternative()
        alternative_so = self.env['sale.order'].browse(alternative_action['res_id'])

        self.assertFalse(copy_so.origin_order_id)
        self.assertFalse(copy_so.subscription_id)
        self.assertEqual(renewal_so.origin_order_id.id, alternative_so.origin_order_id.id)
        self.assertEqual(renewal_so.subscription_id.id, alternative_so.subscription_id.id)

    def test_subscription_state(self):
        # test default value for subscription_state
        sub_1 = self.env['sale.order'].create({
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
        self.assertEqual(sub_1.subscription_state, '1_draft')
        sub_2 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        self.assertFalse(sub_2.subscription_state, )
        sub_2.plan_id = self.plan_month
        sub_2.order_line = [
            (0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 3.0,
                'price_unit': 12,
            })]
        self.assertEqual(sub_2.subscription_state, '1_draft')

        sub_2.write({
            'order_line': False,
            'plan_id': False,
        })
        self.assertFalse(sub_2.is_subscription,
            "Subscription quotation without plan_id isn't a subscription")
        self.assertEqual(sub_2.subscription_state, False,
            "Draft subscription quotation without plan_id should lose subscription_state")
        sub_2.action_confirm()
        self.assertFalse(sub_2.subscription_state,
            "SO without subscription plan should lose subscription_state on confirmation")

    def test_free_subscription(self):
        with freeze_time("2023-01-01"):
            # We don't want to create invoice when the sum of recurring line is 0
            nr_product = self.env['product.template'].create({
                'name': 'Non recurring product',
                'type': 'service',
                'uom_id': self.product.uom_id.id,
                'list_price': 25,
                'invoice_policy': 'order',
            })
            # nr_product.taxes_id = False # we avoid using taxes in this example
            self.sub_product_tmpl.subscription_rule_ids.filtered(
                lambda rule: rule.plan_id == self.plan_month
            ).fixed_price = 25
            self.product2.list_price = -25.0
            # total = 0 & recurring amount = 0
            sub_0_0 = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 2.0,
                    }),
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product2.id,
                        'product_uom_qty': 2.0,
                        'price_unit': -25,
                    })
                ],
            })
            # total = 0 & recurring amount > 0
            sub_0_1 = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    (0, 0, {
                        'product_id': self.product.id,
                        'product_uom_qty': 2.0,
                    }),
                    (0, 0, {
                        'product_id': nr_product.product_variant_id.id,
                        'product_uom_qty': 2.0,
                        'price_unit': -25,
                    })
                ],
            })
            # total > 0 & recurring amount = 0
            sub_1_0 = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    (0, 0, {
                        'product_id': self.product.id,
                        'product_uom_qty': 2.0,
                    }),
                    (0, 0, {
                        'product_id': self.product2.id,
                        'product_uom_qty': 2.0,
                    }),
                    (0, 0, {
                        'product_id': nr_product.product_variant_id.id,
                        'product_uom_qty': 2.0,
                    }),
                ],
            })

            sub_negative_recurring = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    (0, 0, {
                        'product_id': self.product.id,
                        'product_uom_qty': 2.0,
                        'price_unit': -30
                    }),
                    (0, 0, {
                        'product_id': self.product2.id,
                        'product_uom_qty': 2.0,
                        'price_unit': -10
                    }),
                ],
            })

            # negative_nonrecurring_sub
            negative_nonrecurring_sub = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 2.0,
                        'price_unit': -30
                    }),
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product2.id,
                        'product_uom_qty': 2.0,
                        'price_unit': -10
                    }),
                    (0, 0, {
                        'name': nr_product.name,
                        'product_id': nr_product.product_variant_id.id,
                        'product_uom_qty': 4.0,
                    }),
                ],
            })

            (sub_0_0 | sub_0_1 | sub_1_0 | sub_negative_recurring | negative_nonrecurring_sub).order_line.tax_ids = False
            (sub_0_0 | sub_0_1 | sub_1_0 | sub_negative_recurring | negative_nonrecurring_sub).action_confirm()

            invoice_0_0 = sub_0_0._create_recurring_invoice()
            self.assertTrue(sub_0_0.currency_id.is_zero(sub_0_0.amount_total))
            self.assertFalse(invoice_0_0, "Free contract with recurring products should not create invoice")
            self.assertEqual(sub_0_0.order_line.mapped('invoice_status'), ['no', 'no'], 'No invoice needed')

            self.assertTrue(sub_0_1.currency_id.is_zero(sub_0_1.amount_total))
            self.assertTrue(sub_0_1.order_line.filtered(lambda l: l.recurring_invoice).price_subtotal > 0)
            invoice_0_1 = sub_0_1._create_recurring_invoice()
            self.assertEqual(invoice_0_1.amount_total, 0, "Total is 0 but an invoice should be created.")
            self.assertEqual(sub_0_1.order_line.mapped('invoice_status'), ['invoiced', 'invoiced'], 'No invoice needed')

            self.assertTrue(sub_1_0.amount_total > 0)
            invoice_1_0 = sub_1_0._create_recurring_invoice()
            self.assertEqual(invoice_1_0.amount_total, 50, "Total is 0 and an invoice should be created.")
            self.assertEqual(sub_1_0.order_line.mapped('invoice_status'), ['no', 'no', 'invoiced'], 'No invoice needed')
            self.assertFalse(all(invoice_1_0.invoice_line_ids.sale_line_ids.product_id.mapped('recurring_invoice')),
                             "The recurring line should be invoiced")

            # Negative subscription will be invoiced by cron the next day
            negative_invoice = sub_negative_recurring._create_recurring_invoice()
            self.assertEqual(sub_negative_recurring.amount_total, -80)
            self.assertFalse(negative_invoice, "Free contract with recurring products should not create invoice")
            self.assertEqual(sub_negative_recurring.order_line.mapped('invoice_status'), ['no', 'no'], 'No invoice needed')

            negative_non_recurring_inv = negative_nonrecurring_sub._create_recurring_invoice()
            self.assertEqual(negative_nonrecurring_sub.amount_total, 20)
            self.assertFalse(negative_non_recurring_inv, "negative contract with non recurring products should not create invoice")
            self.assertEqual(sub_negative_recurring.order_line.mapped('invoice_status'), ['no', 'no'],
                             'No invoice needed')
            self.assertTrue(negative_nonrecurring_sub.payment_exception, "The contract should be in exception")

    def test_subscription_unlink_flow(self):
        """
            Check that the user receives the correct messages when he deletes a subscription.
            Check that the flow to delete a subscription is confirm => close => cancel
        """
        subscription_a = self.env['sale.order'].create({
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        subscription_b = self.env['sale.order'].create({
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        subscription_c = self.env['sale.order'].create({
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        subscription_d = self.env['sale.order'].create({
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        subscription_a._onchange_sale_order_template_id()
        subscription_b._onchange_sale_order_template_id()
        subscription_c._onchange_sale_order_template_id()
        subscription_d._onchange_sale_order_template_id()
        # Subscription can be deleted if it is in draft
        subscription_a.unlink()
        # Subscription cannot be deleted if it was confirmed once before and it is not closed
        subscription_b.action_confirm()
        with self.assertRaisesRegex(UserError,
            r"Oops! Before you can delete a confirmed subscription, you'll need to close and cancel it."):
            subscription_b.unlink()
        # Subscription cannot be deleted if it is closed
        subscription_c.action_confirm()
        subscription_c.set_close()
        with self.assertRaisesRegex(UserError,
            r'You can not delete a sent quotation or a confirmed sales order. You must first cancel it.'):
            subscription_c.unlink()
        # Subscription can be deleted if it is cancel
        subscription_d.action_confirm()
        subscription_d._action_cancel()
        subscription_d.unlink()

    def test_subscription_change_partner(self):
        # This test check that action_confirm is only called once on SO when the partner is updated.
        sub = self.env['sale.order'].create({
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
        self.assertEqual(sub.partner_id, self.partner)
        sub.action_confirm()
        self.assertEqual(sub.subscription_state, '3_progress')
        action_confirm_orig = SaleOrder.action_confirm
        self.call_count = 0
        self1 = self
        def _action_confirm_mock(*args, **kwargs):
            self1.call_count += 1
            return action_confirm_orig(*args, **kwargs)

        with patch('odoo.addons.sale_subscription.models.sale_order.SaleOrder.action_confirm', _action_confirm_mock):
            sub.partner_id = self.partner_a_invoice.id
            self.assertEqual(sub.partner_id, self.partner_a_invoice)
            self.assertEqual(self.call_count, 0)

    def test_reopen(self):
        with freeze_time("2023-03-01"):
            sub = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 3.0,
                    })],
            })
            sub_mrr_change = sub.copy()
            self.flush_tracking()
            (sub | sub_mrr_change).action_confirm()
            self.flush_tracking()
        with freeze_time("2023-03-02"):
            sub_mrr_change.order_line.product_uom_qty = 10
            sub.order_line.product_uom_qty = 10
            self.flush_tracking()
        with freeze_time("2023-03-05"):
            close_reason_id = self.env.ref('sale_subscription.close_reason_1').id
            (sub | sub_mrr_change).set_close(close_reason_id=close_reason_id)
            self.flush_tracking()
            # We change the quantity after cloing to see what happens to the logs when we reopen
            sub_mrr_change.order_line.product_uom_qty = 6
            self.flush_tracking()
            (sub | sub_mrr_change).set_close()
            self.flush_tracking()
            churn_log = sub.order_log_ids.sorted('event_date')[-1]
            self.assertEqual((churn_log.event_type, churn_log.amount_signed, churn_log.recurring_monthly),
                             ('2_churn', -10, 0), "The churn log should be created")
        with freeze_time("2023-03-10"):
            (sub | sub_mrr_change).reopen_order()
            self.flush_tracking()
            order_log_ids = sub.order_log_ids.sorted('event_date')
            sub_data = [
                (log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly)
                for log in order_log_ids]
            self.assertEqual(sub_data, [('0_creation', datetime.date(2023, 3, 1), '1_draft', 3.0, 3.0),
                                        ('1_expansion', datetime.date(2023, 3, 2), '3_progress', 7.0, 10.0)])
            order_log_ids = sub_mrr_change.order_log_ids.sorted('event_date')
            sub_data = [
                (log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly)
                for log in order_log_ids]

            self.assertEqual(sub_data, [('0_creation', datetime.date(2023, 3, 1), '1_draft', 3.0, 3.0),
                                        ('1_expansion', datetime.date(2023, 3, 2), '3_progress', 7.0, 10.0),
                                        ('15_contraction', datetime.date(2023, 3, 10), '3_progress', -4.0, 6.0)])

    def test_cancel_constraint(self):
        sub_progress = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_month.id,
            'order_line': [
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product.id,
                    'product_uom_qty': 3.0,
                })],
        })
        sub_paused = sub_progress.copy()
        sub_progress_no_invoice = sub_progress.copy()
        with freeze_time('2022-02-02'):
            (sub_progress | sub_paused | sub_progress_no_invoice).action_confirm()
            (sub_progress | sub_paused)._create_recurring_invoice()
        sub_paused.subscription_state = '4_paused'
        sub_progress_no_invoice._action_cancel()
        self.assertEqual(sub_progress_no_invoice.state, 'cancel')
        with self.assertRaises(ValidationError):
            # You cannot cancel a subscription that has been invoiced
            sub_paused._action_cancel()
        sub_paused.subscription_state = '6_churn'
        self.assertEqual(sub_paused.state, 'sale')
        sub_progress.subscription_state = '6_churn'
        sub_progress._action_cancel()
        sub_progress.set_open()
        action = sub_progress.prepare_renewal_order()
        renewal_so = self.env['sale.order'].browse(action['res_id'])
        renewal_so.action_confirm()
        self.assertEqual(sub_progress.subscription_state, '5_renewed', "sub was renewed")
        inv = renewal_so._create_invoices()
        inv._post()
        self.assertEqual(renewal_so.subscription_state, '3_progress')
        action = renewal_so.prepare_renewal_order()
        renewal_so2 = self.env['sale.order'].browse(action['res_id'])
        renewal_so2.action_confirm()
        self.assertEqual(renewal_so2.subscription_state, '3_progress')
        self.assertEqual(renewal_so.subscription_state, '5_renewed')
        self.assertEqual(renewal_so.state, 'sale')
        self.assertTrue(renewal_so.locked)
        with self.assertRaises(ValidationError):
            # You cannot cancel a subscription that has been invoiced
            renewal_so._action_cancel()

    def test_protected_close_reason(self):
        close_reason = self.env['sale.order.close.reason'].create({
            'name': 'Super close reason',
            'is_protected': True,
        })

        with self.assertRaises(AccessError):
            close_reason.unlink()

    def test_close_reason_end_of_contract(self):
        sub = self.subscription
        end_date = datetime.date(2022, 6, 20)
        sub.end_date = end_date
        with freeze_time(end_date):
            sub.action_confirm()
            sub._create_recurring_invoice()
        self.assertEqual(sub.close_reason_id.id, self.env.ref('sale_subscription.close_reason_end_of_contract').id)

    def test_close_reason_automatic_renewal_failed(self):
        sub = self.subscription
        sub.plan_id.auto_close_limit = 1
        start_date = datetime.date(2022, 6, 20)
        sub.start_date = start_date
        sub.payment_token_id = self.payment_token.id
        sub.action_confirm()

        with freeze_time(start_date + relativedelta(days=sub.plan_id.auto_close_limit)):
            with patch('odoo.addons.sale_subscription.models.sale_order.SaleOrder._do_payment', wraps=self._mock_subscription_do_payment_rejected):
                sub._create_recurring_invoice()
        self.assertEqual(sub.close_reason_id.id, self.env.ref('sale_subscription.close_reason_auto_close_limit_reached').id)

    def test_subscription_pricelist_discount(self):
        self.pricelist.item_ids = [
            Command.create({
                'compute_price': 'percentage',
                'percent_price': 50,
            })
        ]
        sub = self.env["sale.order"].with_context(**self.context_no_mail).create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'note': "original subscription description",
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
            'pricelist_id': self.pricelist.id,
        })
        sub._onchange_sale_order_template_id()
        self.assertTrue(sub.order_line[0].pricelist_item_id.plan_id)
        self.assertFalse(sub.order_line[1].pricelist_item_id.plan_id)
        self.assertEqual(
            sub.order_line.mapped('discount'),
            [0, 0],
            "Regular pricelist discounts should't affect temporal items."
        )
        sub.order_line = [Command.create({
            'product_id': self.product_a.id, # non-subscription product
        })]
        self.assertEqual(
            sub.order_line.mapped('discount'),
            [0, 0, 50],
            "Regular pricelist discounts should't affect temporal items.",
        )
        sub.order_line.discount = 20
        self.assertEqual(sub.order_line.mapped('discount'), [20, 20, 20])
        sub.action_confirm()
        self.assertEqual(sub.order_line.mapped('discount'), [20, 20, 20],
             "Discounts should not be reset on confirmation.")
        self.pricelist.item_ids = [
            Command.create({
                'compute_price': 'percentage',
                'percent_price': 50,
                'plan_id': self.plan_month.id,
            })
        ]
        sub._recompute_prices()
        self.assertEqual(
            sub.order_line.mapped('discount'),
            [0, 50, 50],
            'Recurring pricing discounts should apply to recurring lines',
        )

    def test_non_subscription_pricelist_discount(self):
        pricelist = self.pricelist
        pricelist.item_ids = [
            Command.create({
                'compute_price': 'percentage',
                'percent_price': 50,
            })
        ]
        so = self.env["sale.order"].with_context(**self.context_no_mail).create({
            'name': 'TestNonSubscription',
            'is_subscription': False,
            'partner_id': self.user_portal.partner_id.id,
            'pricelist_id': pricelist.id,
            'order_line': [(0, 0, {'product_id': self.product_a.id})],
        })
        self.assertEqual(so.order_line.discount, 50)
        so.order_line.discount = 20
        self.assertEqual(so.order_line.discount, 20)
        so.action_confirm()
        self.assertEqual(so.order_line.discount, 20,
             "Discounts should not be reset on confirmation.")

    def test_paused_resume_logs(self):
        self.flush_tracking()
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
        self.flush_tracking()
        sub.action_confirm()
        self.flush_tracking()
        sub.pause_subscription()
        self.flush_tracking()
        sub.pause_subscription()
        self.flush_tracking()
        sub.resume_subscription()
        self.flush_tracking()
        order_log_ids = sub.order_log_ids.sorted('id')
        sub_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly)
                    for log in order_log_ids]
        self.assertEqual(sub_data, [('0_creation', today, '1_draft', 21, 21)])

    def test_close_reason_wizard(self):
        self.subscription._onchange_sale_order_template_id()
        self.subscription.action_confirm()
        self.subscription._create_recurring_invoice()
        new_reason = self.env['sale.order.close.reason'].create({'name': "test reason"})
        wiz = self.env['sale.subscription.close.reason.wizard'].with_context(active_id=self.subscription.id).create({
            'close_reason_id': new_reason.id
        })
        wiz.set_close()
        self.assertEqual(self.subscription.close_reason_id, new_reason, "The reason should be saved on the order")

    def test_plan_field_automatic_price_unit_update(self):
        """
        Assert that after changing the 'Recurrence' field of a subscription,
        prices will recompute automatically ONLY for subscription products.
        """
        self._enable_currency('EUR')
        self.env['product.pricelist.item'].create([
            {
                'plan_id': self.plan_month.id,
                'fixed_price': 100,
            }, {
                'plan_id': self.plan_year.id,
                'fixed_price': 1000,
            },
        ])
        simple_product = self.product.copy({'recurring_invoice': False})
        sub_product_tmpl = self.env['product.template'].create({
            'name': 'BaseTestProduct',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.uom_unit.id,
        })
        sub = self.subscription.create({
            'name': 'Company1 - Currency1',
            'partner_id': self.user_portal.partner_id.id,
            'plan_id': self.plan_month.id,
            'order_line': [
                Command.create({
                    'product_id': sub_product_tmpl.product_variant_id.id,
                }),
                Command.create({
                    'product_id': simple_product.id,
                    'product_uom_qty': 2.0,
                })
            ]
        })
        sub.action_confirm()
        self.flush_tracking()
        # Assert that order lines were created with correct pricing and currency.
        self.assertEqual(sub.order_line[0].price_unit, 100.0, "Subscription product's order line should have its price unit as 100.0 according to the 'Monthly' pricing during creation.")
        self.assertEqual(sub.order_line[1].price_unit, 50.0, "Simple product's order line must have its default price unit of 50.0 during creation.")

        # Change the 'Recurrence' field and check if price unit updated ONLY in the recurring order line.
        sub.plan_id = self.plan_year.id
        self.assertEqual(sub.order_line[0].price_unit, 1000.0, "Subscription product's order line must have its unit price as 1000.0 after 'Recurrence' is changed to 'Yearly'.")
        self.assertEqual(sub.order_line[1].price_unit, 50.0, "Simple product's order line must not update its price unit, it must be kept as 50.0 during the 'Recurrence' field changes.")

        # Update price of normal product and check if it is updated in recurrence (it should not!)
        sub.order_line[1].product_id.list_price = 70.0
        self.assertEqual(sub.order_line[1].price_unit, 50.0, "Simple product's price unit must be kept as 50.0 even though the product price was updated outside the subscription scope.")
        self.env['sale.order']._cron_recurring_create_invoice()
        self.flush_tracking()

        # Change again the 'Recurrence' field and check if the price unit update during renewal was done in the recurring order line.
        action = sub.prepare_renewal_order()
        renewal_so = self.env['sale.order'].browse(action['res_id'])
        renewal_so.plan_id = self.plan_month.id
        self.assertEqual(renewal_so.order_line[0].price_unit, 100.0, "Subscription product's order line must have its unit price as 100.0 after 'Recurrence' is changed to 'Monthly'.")

        # Change the 'Recurrence' field to yearly and ensure that price was updated accordingly for the subscription product.
        renewal_so.plan_id = self.plan_year.id
        self.assertEqual(renewal_so.order_line[0].price_unit, 1000.0, "Subscription product's order line must have its unit price as 1000.0 after 'Recurrence' is changed to 'Yearly'.")

    def test_new_plan_id_optional_products_price_update(self):
        """
        Assert that after changing the 'Recurrence' field of a subscription, prices will be recomputed
        for Optional Products with time-based pricing in the subscription template.
        """
        # Define a subscription template with a optional product having time-based pricing.
        self.product.product_tmpl_id.subscription_rule_ids = [
            Command.clear(),
            Command.create({
                'fixed_price': 150,
                'plan_id': self.plan_month.id,
            }),
            Command.create({
                'fixed_price': 1000,
                'plan_id': self.plan_year.id,
            })
        ]
        template = self.env['sale.order.template'].create({
            'name': 'Subscription template with time-based pricing on optional product',
            'note': "This is the template description",
            'plan_id': self.plan_year.id,
            'sale_order_template_line_ids': [
                Command.create({
                    'name': "monthly",
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'product_uom_id': self.product.uom_id.id
                }),
                Command.create({
                    'name': "Optional Products",
                    'display_type': 'line_section',
                    'is_optional': True,
                }),
                Command.create({
                    'name': "line 1",
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'product_uom_id': self.product.uom_id.id,
                })
            ],
        })
        # Create the subscription based on the subscription template.
        subscription = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'partner_id': self.user_portal.partner_id.id,
            'plan_id': self.plan_month.id,
            'sale_order_template_id': template.id,
        })
        subscription._onchange_sale_order_template_id()

        optional_lines = self._get_optional_product_lines(subscription)
        # Assert that optional product has its price updated after changing the 'recurrence' field.
        self.assertEqual(optional_lines.price_unit, 150, "The price unit for the optional product must be 150.0 due to 'Monthly' value in the 'Recurrence' field.")
        subscription.plan_id = self.plan_year.id
        self.assertEqual(optional_lines.price_unit, 1000, "The price unit for the optional product must update to 1000.0 after changing the 'Recurrence' field to 'Yearly'.")

    def test_negative_subscription(self):
        nr_product = self.env['product.template'].create({
            'name': 'Non recurring product',
            'type': 'service',
            'uom_id': self.product.uom_id.id,
            'list_price': 25,
            'invoice_policy': 'order',
        })
        self.product2.list_price = -25.0
        self.product.subscription_rule_ids.unlink()
        self.sub_product_tmpl.list_price = -30
        self.product_tmpl_2.list_price = -10
        sub_negative_recurring = self.env['sale.order'].create({
            'name': 'sub_negative_recurring (1)',
            'partner_id': self.partner.id,
            'plan_id': self.plan_month.id,
            'order_line': [
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product.id,
                    'product_uom_qty': 2.0,
                }),
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product2.id,
                    'product_uom_qty': 2.0,
                }),
            ],
        })
        negative_nonrecurring_sub = self.env['sale.order'].create({
            'name': 'negative_nonrecurring_sub (2)',
            'partner_id': self.partner.id,
            'plan_id': self.plan_month.id,
            'order_line': [
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product.id,
                    'product_uom_qty': 2.0,
                }),
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product2.id,
                    'product_uom_qty': 2.0,
                }),
                (0, 0, {
                    'name': nr_product.name,
                    'product_id': nr_product.product_variant_id.id,
                    'product_uom_qty': 4.0,
                }),
            ],
        })
        all_subs = sub_negative_recurring | negative_nonrecurring_sub
        with freeze_time("2023-01-01"):
            self.flush_tracking()
            all_subs.write({'start_date': False, 'next_invoice_date': False})
            all_subs.action_confirm()
            self.flush_tracking()
            all_subs.next_invoice_date = datetime.datetime(2023, 2, 1)
            self.flush_tracking()
        with freeze_time("2023-02-01"):
            sub_negative_recurring.order_line.product_uom_qty = 6 # update quantity
            negative_nonrecurring_sub.order_line[1].product_uom_qty = 4
            self.flush_tracking()
            all_subs._create_recurring_invoice() # should not create any invoice because negative
            self.flush_tracking()

        with freeze_time("2023-02-15"):
            action = sub_negative_recurring.prepare_renewal_order()
            renewal_so1 = self.env['sale.order'].browse(action['res_id'])
            renewal_so1.name = 'renewal_so1'
            renewal_so1.order_line.product_uom_qty = 12
            action = negative_nonrecurring_sub.prepare_renewal_order()
            renewal_so2 = self.env['sale.order'].browse(action['res_id'])
            renewal_so2.name = 'renewal_so2'
            renewal_so2.order_line[1].product_uom_qty = 8
            self.flush_tracking()
            all_subs |= renewal_so1|renewal_so2
            (renewal_so1|renewal_so2).action_confirm()
            self.flush_tracking()
        with freeze_time("2023-03-01"):
            (all_subs)._create_recurring_invoice()
            self.flush_tracking()
        with freeze_time("2023-04-01"):
            self.flush_tracking()
            self.assertFalse(renewal_so2.invoice_ids, "no invoice should have been created")
            close_reason_id = self.env.ref('sale_subscription.close_reason_1').id
            renewal_so2.set_close(close_reason_id=close_reason_id)
            self.flush_tracking()
            renewal_so2.reopen_order()
            self.flush_tracking()


        order_log_ids = self.env['sale.order.log'].search([('order_id', 'in', (sub_negative_recurring|renewal_so1).ids)], order='id')
        sub_data1 = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly)
                    for log in order_log_ids]
        self.assertEqual(sub_data1, [('0_creation', datetime.date(2023, 1, 1), '1_draft', 0, 0),
                                     ('3_transfer', datetime.date(2023, 2, 15), '5_renewed', 0, 0),
                                     ('3_transfer', datetime.date(2023, 2, 15), '2_renewal', 0, 0)])

        order_log_ids = self.env['sale.order.log'].search([('order_id', 'in', (negative_nonrecurring_sub|renewal_so2).ids)], order='id')
        sub_data2 = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly)
                    for log in order_log_ids]
        self.assertEqual(sub_data2, [('0_creation', datetime.date(2023, 1, 1), '1_draft', 0, 0),
                                     ('3_transfer', datetime.date(2023, 2, 15), '5_renewed', 0, 0),
                                     ('3_transfer', datetime.date(2023, 2, 15), '2_renewal', 0, 0)])
        self.assertEqual(renewal_so1.recurring_monthly, -480, "The MRR field is negative but it does not produce logs")
        self.assertEqual(renewal_so2.recurring_monthly, -140, "The MRR field is negative but it does not produce logs")

    def test_recurring_plan_price_recalc_adding_optional_product(self):
        """
        Test that when an optional recurring product is added to a subscription sale order that its price unit is
        correctly recalculated after subsequent edits to the order's recurring plan
        """
        self.sub_product_tmpl.write({'subscription_rule_ids': [
            Command.set([]), Command.create({'plan_id': self.plan_year.id, 'fixed_price': 100})
        ]})
        product_a = self.sub_product_tmpl.product_variant_id
        product_a.list_price = 1.0

        self.product_tmpl_2.write({'subscription_rule_ids': [
            Command.set([]), Command.create({'plan_id': self.plan_year.id, 'fixed_price': 200})
        ]})
        product_b = self.product_tmpl_2.product_variant_id
        product_b.list_price = 1.0

        sale_order = self.env['sale.order'].create({
            'plan_id': self.plan_month.id,
            'partner_id': self.user_portal.partner_id.id,
            'company_id': self.company_data['company'].id,
            'order_line': [
                Command.create({'product_id': product_a.id}),
                Command.create({
                    'name': 'Optional products',
                    'display_type': 'line_section',
                    'is_optional': True,
                }),
                Command.create({
                    'product_id': product_b.id,
                }),
            ],
        })

        sale_order.write({'plan_id': self.plan_year})

        self.assertEqual(sale_order.order_line[2].price_unit, 200.0)

    def test_subscription_lock_settings(self):
        """ The settings to automatically lock SO upon confirmation
        should never be applied to subscription orders. """
        self.env.user.group_ids += self.env.ref('sale.group_auto_done_setting')
        self.subscription.write({'start_date': False, 'next_invoice_date': False})
        self.subscription.action_confirm()
        self.assertEqual(self.subscription.state, 'sale')

    def test_formatted_read_group_sale_subscription(self):
        self.subscription.action_confirm()
        SaleSubscription = self.env['sale.order']
        domain = ['&', ['subscription_state', 'not in', ['2_renewal', '5_renewed', '7_upsell', False]], '|', ['subscription_state', '=', '3_progress'], ['subscription_state', '=', '4_paused']]
        aggregates = ['rating_last_value:sum', 'recurring_total:sum', '__count']
        groupby = ['subscription_state']
        result = SaleSubscription.with_context(read_group_expand=True).formatted_read_group(domain, groupby, aggregates)

        self.assertEqual(result[0]['__count'], 1)
        self.assertEqual(result[0]['subscription_state'], '3_progress')
        self.assertEqual(result[1]['__count'], 0)
        self.assertEqual(result[1]['subscription_state'], '4_paused')

    def test_subscription_confirm_update_salesperson_on_partner(self):
        """ confirming sale order should update the salesperson on related partner. """
        self.assertFalse(self.subscription.partner_id.user_id)
        self.subscription.action_confirm()
        self.assertEqual(self.subscription.user_id, self.subscription.partner_id.user_id, "Salesperson on subscription and partner should be same")

    def test_subscription_salesperson_changes_partner_saleperson(self):
        """ changing salesperson on confirmed subscription should change salesperson on related partner. """
        self.subscription.action_confirm()
        self.assertEqual(self.subscription.user_id, self.subscription.partner_id.user_id, "Salesperson on subscription and partner should be same")

        new_user = self.env['res.users'].create({
            'name': 'new user',
            'login': 'new',
            'email': 'new@test.com',
        })
        self.subscription.write({'user_id': new_user.id})
        self.assertEqual(new_user, self.subscription.partner_id.user_id, "Subscription's salesperson should be updated on partner's salesperson")
        self.assertIn(new_user.partner_id.id, self.subscription.message_follower_ids.partner_id.ids)

        new_user_2 = self.env['res.users'].create({
            'name': 'new user 2',
            'login': 'new2',
            'email': 'new2@test.com',
        })
        self.subscription.write({'user_id': new_user_2.id})
        self.assertEqual(new_user_2, self.subscription.partner_id.user_id, "Subscription's salesperson should be updated on partner's salesperson")
        self.assertNotIn(new_user.partner_id.id, self.subscription.message_follower_ids.partner_id.ids, "Old salesperson should removed from message followers")

    def test_recurring_invoice_cron_trigger(self):
        """
        Test that the cron job to create recurring invoices is triggered only
        when count of subscriptions to invoice is greater than batch size.
        """
        SaleOrder = self.env['sale.order']
        with freeze_time("2024-05-01"):
            subscriptions = []
            for i in range (4):
                subscriptions.append(SaleOrder.create({
                    'name': 'require payment %s' % str(i),
                    'is_subscription': True,
                    'partner_id': self.user_portal.partner_id.id,
                    'plan_id': self.plan_month.id,
                    'order_line': [
                        Command.create({
                            'product_id': self.product.id,
                            'product_uom_qty': 1
                        }),
                    ],
                    'require_payment': True,
                }))
                subscriptions[-1].action_confirm()

            # no subscription should be invoiced which means we should not trigger cron job
            all_subscriptions, need_cron_trigger = SaleOrder._recurring_invoice_get_subscriptions(batch_size=3)
            self.assertFalse(need_cron_trigger)
            self.assertFalse(all_subscriptions)

    def test_recurring_invoice_cron_batch(self):
        """
        Check all subscriptions are processed by the cron when there are more than batch_size of them and
        some of them are filtered by _get_subscriptions_to_invoice.
        """
        SaleOrder = self.env['sale.order']
        subscriptions_to_invoice = self.env['sale.order']

        for i in range(5):
            sub_to_invoice = SaleOrder.create({
                'name': 'Payment not required',
                'is_subscription': True,
                'partner_id': self.user_portal.partner_id.id,
                'pricelist_id': self.pricelist.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_qty': 1
                    }),
                ],
                'require_payment': False,
            })
            sub_to_invoice.action_confirm()
            subscriptions_to_invoice += sub_to_invoice

        for i in range(2):
            sub = SaleOrder.create({
                'name': 'require payment %s' % str(i),
                'is_subscription': True,
                'partner_id': self.user_portal.partner_id.id,
                'pricelist_id': self.pricelist.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_qty': 1
                    }),
                ],
                'require_payment': True,
            })
            sub.action_confirm()

        SaleOrder._create_recurring_invoice(batch_size=3)

        self.assertTrue(all(sub.invoice_ids))

    def test_amount_to_invoice_with_subscription(self):
        one_shot_product_tmpl = self.env['product.template'].create({
            'name': 'One shot product',
            'type': 'service',
            'recurring_invoice': False,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        one_shot_product = one_shot_product_tmpl.product_variant_id
        one_shot_product.write({
            'taxes_id': [Command.set([self.tax_10.id])],
            'property_account_income_id': self.account_income.id,
        })

        with freeze_time('2024-01-01'):
            # Create a monthly subscription
            sub = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'sale_order_template_id': self.subscription_tmpl.id,
                'is_subscription': True,
                'plan_id': self.plan_month.id,
                'order_line': [
                    # Recurring product
                    Command.create({
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 1.0,
                        'price_unit': 100,
                    }),
                    # Non-recurring product
                    Command.create({
                        'name': one_shot_product.name,
                        'product_id': one_shot_product.id,
                        'product_uom_qty': 2.0,
                        'price_unit': 50,
                    }),
                ]
            })
            sub.action_confirm()

            # Nothing has been invoiced --> total amount is due
            self.assertEqual(sub.amount_to_invoice, 220.0)
            posted_invoice_lines = sub.order_line.invoice_lines.filtered(lambda line: line.parent_state == 'posted')
            self.assertEqual(sum(posted_invoice_lines.mapped('price_total')), 0.0)

            sub._create_recurring_invoice()

            # First invoice created, which includes both recurring and non-recurring products
            self.assertEqual(sub.amount_to_invoice, 0.0)
            posted_invoice_lines = sub.order_line.invoice_lines.filtered(lambda line: line.parent_state == 'posted')
            self.assertEqual(sum(posted_invoice_lines.mapped('price_total')), 220.0)

        with freeze_time('2024-02-01'):
            # Invalidate the cache to force the re-computation of the un-invoiced balance with the new date.
            # It should be equal to the recurring amount, i.e. 110.0
            sub.invalidate_recordset(['amount_to_invoice'])
            sub.order_line.invalidate_recordset(['amount_to_invoice'])
            self.assertEqual(sub.amount_to_invoice, 110.0)

            sub._create_recurring_invoice()

            # Second invoice created, which only includes the recurring product
            self.assertEqual(sub.amount_to_invoice, 0.0)
            posted_invoice_lines = sub.order_line.invoice_lines.filtered(lambda line: line.parent_state == 'posted')
            self.assertEqual(sum(posted_invoice_lines.mapped('price_total')), 330.0)

    def test_subscription_online_payment_no_token(self):
        with freeze_time("2024-05-01"):
            self.subscription.require_payment = True
            self.subscription.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()
            # it should not create a invoice
            self.assertEqual(self.subscription.invoice_count, 0)

        with self.mock_mail_gateway():
            with freeze_time("2024-04-17"):
                self.env['sale.order']._cron_recurring_send_payment_reminder()
                # it will send payment reminder mail to customer before 14
                self.assertEqual(len(self._new_mails), 1)
                self.assertEqual(self.subscription.last_reminder_date, fields.Date.today())
            with freeze_time("2024-04-24"):
                self.env['sale.order']._cron_recurring_send_payment_reminder()
                # it will send payment reminder mail to customer before 7 days
                self.assertEqual(len(self._new_mails), 2)
                self.assertEqual(self.subscription.last_reminder_date, fields.Date.today())
            with freeze_time("2024-04-29"):
                self.env['sale.order']._cron_recurring_send_payment_reminder()
                # it will send payment reminder mail to customer before 2 days
                self.assertEqual(len(self._new_mails), 3)
                self.assertEqual(self.subscription.last_reminder_date, fields.Date.today())
            with freeze_time("2024-05-01"):
                self.env['sale.order']._cron_recurring_send_payment_reminder()
                # it will send payment reminder mail to customer
                self.assertEqual(len(self._new_mails), 4)
                self.assertEqual(self.subscription.last_reminder_date, fields.Date.today())
            with freeze_time("2024-05-03"):
                self.env['sale.order']._cron_recurring_send_payment_reminder()
                # it will send payment reminder mail to customer
                self.assertEqual(len(self._new_mails), 5)
                self.assertEqual(self.subscription.last_reminder_date, fields.Date.today())
            with freeze_time("2024-05-08"):
                self.env['sale.order']._cron_recurring_send_payment_reminder()
                # it will send payment reminder mail to customer
                self.assertEqual(len(self._new_mails), 6)
                self.assertEqual(self.subscription.last_reminder_date, fields.Date.today())
            with freeze_time("2024-05-15"):
                self.env['sale.order']._cron_recurring_send_payment_reminder()
                # it will send payment reminder mail to customer
                self.assertEqual(len(self._new_mails), 7)
                self.assertEqual(self.subscription.last_reminder_date, fields.Date.today())
            with freeze_time("2024-05-16"):
                self.env['sale.order']._cron_recurring_send_payment_reminder()
                # it should close the subscription
                self.assertEqual(self.subscription.subscription_state, '6_churn')

    def test_cron_recurring_send_payment_reminder_failure(self):
        with freeze_time("2024-05-01"):
            self.subscription.require_payment = True
            self.subscription.action_confirm()
        with self.mock_mail_gateway():
            with freeze_time("2024-04-17"):
                self.env.ref('sale_subscription.send_payment_reminder').lastcall = False
                self.env['sale.order']._cron_recurring_send_payment_reminder()
                self.assertEqual(self.subscription.last_reminder_date, fields.Date.today())
                self.assertEqual(len(self._new_mails), 1)
            with freeze_time("2024-04-25"):
                # we will set lastcall of cron to 23/4.
                # if cron run on 24/4 then it should send reminder on that day but we skip 24/4 and run the cron on 25/4
                # it should send reminder mail on 25/4 as the cron failed to run on 24/4.
                self.env.ref('sale_subscription.send_payment_reminder').lastcall = datetime.datetime(2024, 4, 23, 0, 0, 0)
                self.env['sale.order']._cron_recurring_send_payment_reminder()
                self.assertEqual(self.subscription.last_reminder_date, fields.Date.today())
                self.assertEqual(len(self._new_mails), 2)

    def test_subscription_recurring_invoice_and_reminder_domain(self):
        SaleOrder = self.env['sale.order']
        with freeze_time("2024-05-01"):
            sub_1 = SaleOrder.create({
                'name': 'with token and online payment true',
                'is_subscription': True,
                'partner_id': self.user_portal.partner_id.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_qty': 1
                    }),
                ],
                'require_payment': True,
                'payment_token_id': self.payment_token.id,
            })
            sub_1.action_confirm()

            sub_2 = SaleOrder.create({
                'name': 'without token and online payment true',
                'is_subscription': True,
                'partner_id': self.user_portal.partner_id.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_qty': 1
                    }),
                ],
                'require_payment': True,
            })
            sub_2.action_confirm()

            sub_3 = SaleOrder.create({
                'name': 'with token and online payment false',
                'is_subscription': True,
                'partner_id': self.user_portal.partner_id.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_qty': 1
                    }),
                ],
                'payment_token_id': self.payment_token.id,
            })
            sub_3.action_confirm()

            sub_4 = SaleOrder.create({
                'name': 'without token and online payment false',
                'is_subscription': True,
                'partner_id': self.user_portal.partner_id.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_qty': 1
                    }),
                ],
            })
            sub_4.action_confirm()

            sub_5 = SaleOrder.create({
                'name': 'without token online payment true and prepayment percent < 100',
                'is_subscription': True,
                'partner_id': self.user_portal.partner_id.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_qty': 1
                    }),
                ],
                'require_payment': True,
                'prepayment_percent': 0.5,
            })
            sub_5.action_confirm()

            sub_6 = SaleOrder.create({
                'name': 'with token online payment true and prepayment percent < 100',
                'is_subscription': True,
                'partner_id': self.user_portal.partner_id.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_qty': 1
                    }),
                ],
                'require_payment': True,
                'prepayment_percent': 0.5,
                'payment_token_id': self.payment_token.id,
            })
            sub_6.action_confirm()

            # filter out subscription for which "_create_recurring_invoice" cron should run
            all_subscriptions, need_cron_trigger = SaleOrder._recurring_invoice_get_subscriptions()
            self.assertFalse(need_cron_trigger)
            self.assertEqual([sub_6.id, sub_5.id, sub_4.id, sub_3.id, sub_1.id], all_subscriptions.ids, "subscriptions are not filtered correctly.")
            self.assertNotIn(sub_2.id, all_subscriptions.ids, "second subscription should not filtered in this domain")

            # filter out subscription for which "_cron_recurring_send_payment_reminder" cron should run
            parameters = SaleOrder._subscription_reminder_parameters()
            send_reminder_sub = SaleOrder.search(parameters['domain'])
            self.assertEqual([sub_5.id, sub_2.id], send_reminder_sub.ids, "subscriptions are not filtered correctly.")

            # run both the crons
            with patch('odoo.addons.sale_subscription.models.sale_order.SaleOrder._do_payment', wraps=self._mock_subscription_do_payment):
                SaleOrder._cron_recurring_create_invoice()
                sub_1.transaction_ids._get_last()._post_process()
                sub_3.transaction_ids._get_last()._post_process()
                sub_6.transaction_ids._get_last()._post_process()
            SaleOrder._cron_recurring_send_payment_reminder()

        with freeze_time("2024-05-03"):
            # Filter out subscription for which "_create_recurring_invoice" cron should run
            all_subscriptions, need_cron_trigger = SaleOrder._recurring_invoice_get_subscriptions()
            self.assertFalse(need_cron_trigger)
            # No subscription should be filterd out.
            self.assertFalse(all_subscriptions, "subscriptions are not filtered correctly.")

            # Filter out subscription for which "_cron_recurring_send_payment_reminder" cron should run
            parameters = SaleOrder._subscription_reminder_parameters()
            send_reminder_sub = SaleOrder.search(parameters['domain'])
            self.assertEqual([sub_2.id], send_reminder_sub.ids, "subscriptions are not filtered correctly.")

            SaleOrder._cron_recurring_send_payment_reminder()

        with freeze_time("2024-06-01"):
            # filter out subscription for which "_create_recurring_invoice" cron should run
            all_subscriptions, need_cron_trigger = SaleOrder._recurring_invoice_get_subscriptions()
            self.assertFalse(need_cron_trigger)
            # sub 5 should be invoiced only for first time after we will send email for payment reminder
            self.assertEqual([sub_6.id, sub_4.id, sub_3.id, sub_1.id], all_subscriptions.ids, "subscriptions are not filtered correctly.")
            self.assertNotIn([sub_5.id, sub_2.id], all_subscriptions.ids, "second subscription should not filtered in this domain")

            # filter out subscription for which "_cron_recurring_send_payment_reminder" cron should run
            parameters = SaleOrder._subscription_reminder_parameters()
            send_reminder_sub = SaleOrder.search(parameters['domain'])
            self.assertEqual([sub_5.id, sub_2.id], send_reminder_sub.ids, "subscriptions are not filtered correctly.")

            # run both the crons
            with patch('odoo.addons.sale_subscription.models.sale_order.SaleOrder._do_payment', wraps=self._mock_subscription_do_payment):
                SaleOrder._cron_recurring_create_invoice()
                sub_1.transaction_ids._get_last()._post_process()
                sub_3.transaction_ids._get_last()._post_process()
                sub_6.transaction_ids._get_last()._post_process()

            SaleOrder._cron_recurring_send_payment_reminder()

    def test_compute_last_invoiced_date(self):
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
            inv = subscription._create_recurring_invoice()
            self.assertEqual(subscription.order_line.last_invoiced_date, datetime.date(2024, 9, 30), "Last invoiced date is updated")
            self.assertEqual(subscription.next_invoice_date, datetime.date(2024, 10, 1), "Next invoice date is updated")

        with freeze_time("2024-10-01"):
            inv = subscription._create_recurring_invoice()
            self.assertEqual(subscription.next_invoice_date, datetime.date(2024, 11, 1), "Next invoice date is updated")
            self.assertEqual(subscription.order_line.last_invoiced_date, datetime.date(2024, 10, 31), "Last invoiced date is updated")

        with freeze_time("2024-10-05"):
            inv.button_draft()
            self.assertEqual(subscription.order_line.last_invoiced_date, datetime.date(2024, 9, 30), "Last invoiced date is reset to previous value")
            inv.button_cancel()
            # user update the next invoice date to recreate it
            subscription.next_invoice_date = datetime.date(2024, 10, 1)

        # with freeze_time("2024-11-01"):
            self.assertEqual(subscription.order_line.last_invoiced_date, datetime.date(2024, 9, 30), "Last invoiced date is unchanged")
            inv = subscription._create_recurring_invoice()
            self.assertEqual(subscription.order_line.last_invoiced_date, datetime.date(2024, 10, 31), "Last invoiced date is updated")

        with freeze_time("2024-12-01"):
            inv = subscription._create_recurring_invoice()
            self.assertEqual(subscription.order_line.last_invoiced_date, datetime.date(2024, 11, 30), "Last invoiced date is updated")
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
            # user update the next invoice date to recreate it
            subscription.next_invoice_date = datetime.date(2024, 11, 1)
            self.assertEqual(subscription.order_line.last_invoiced_date, datetime.date(2024, 10, 31), "Last invoiced date is reverted")
            inv = subscription._create_recurring_invoice()
            self.assertEqual(subscription.order_line.last_invoiced_date, datetime.date(2024, 11, 30), "Last invoiced date is updated")

    def test_invoiced_log(self):
        # make sure that invoiced log are counted but not manual changes
        context_mail = {'tracking_disable': False}
        with freeze_time("2025-01-01"):
            subscription = self.env['sale.order'].with_context(context_mail).create({
                'name': 'Parent Sub',
                'is_subscription': True,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'sale_order_template_id': self.subscription_tmpl.id,
            })
            self.cr.precommit.clear()
            subscription.write({'order_line': [(0, 0, {
                'name': 'TestRecurringLine',
            'product_id': self.product.id,
                'product_uom_qty': 1,
            })]})
            subscription.action_confirm()
            self.flush_tracking()
            self.assertFalse(subscription.order_log_ids.filtered(lambda l: l.effective_date))
            inv = self.env['sale.order']._cron_recurring_create_invoice()
        with freeze_time("2025-01-02"):
            self.assertEqual(subscription.order_log_ids.filtered(lambda l: l.effective_date).effective_date, datetime.date(2025, 1, 1), "one log is counted")

        with freeze_time("2025-01-10"):
            # update the quantity without upselling. This is a manual change.
            previous_logs = subscription.order_log_ids
            subscription.order_line.filtered('product_id').product_uom_qty = 3
            self.flush_tracking()
            first_manual_logs = subscription.order_log_ids - previous_logs
            self.assertFalse(first_manual_logs.effective_date, "other manual log is assimited to the upsell log.")

        with freeze_time("2025-01-15"):
            action = subscription.with_context(tracking_disable=False).prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            upsell_so = upsell_so.with_context(tracking_disable=False)
            upsell_so.order_line.filtered('product_id').product_uom_qty = 3
            upsell_so.name = "Upsell"
            self.flush_tracking()
            previous_logs = subscription.order_log_ids
            subscription.order_line.filtered('product_id').product_uom_qty = 5
            self.flush_tracking()
            second_manual_logs = subscription.order_log_ids - previous_logs
            previous_logs = subscription.order_log_ids
            upsell_so.action_confirm() # new log should have effective_date only when the upsell is invoiced
            self.flush_tracking()
            upsell_logs = subscription.order_log_ids - previous_logs
            inv = upsell_so._create_invoices()
            inv._post()
            self.flush_tracking() #make sure to launch _update_effective_date
            self.assertEqual(upsell_logs.effective_date, datetime.date(2025, 1, 15))
            self.assertFalse(second_manual_logs.effective_date, "last manual update is not invoiced")

        with freeze_time("2025-02-01"):
            action = subscription.with_context(tracking_disable=False).prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so = renewal_so.with_context(tracking_disable=False)
            renewal_so.order_line.filtered('product_id').product_uom_qty = 10
            renewal_so.name = "Renewal"
            self.flush_tracking()
            previous_logs = (subscription + renewal_so).order_log_ids
            renewal_so.action_confirm()
            self.flush_tracking()
            renew_logs = renewal_so.order_log_ids - previous_logs
            self.assertFalse(any(renew_logs.mapped('effective_date')))
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(renew_logs.mapped('effective_date'), [datetime.date(2025, 2, 1), datetime.date(2025, 2, 1)], "Transfer logs share the move date")
            # self.assertEqual(first_manual_logs.effective_date, datetime.date(2025, 2, 1), "Previous manual log is effective at renewal date")

    @freeze_time('2024-08-13')
    def test_uninvoiced_upsell_close_log(self):
        """ Test that the behaviour of effective date is correct even if some items are non invoiced (no effective date).
            Uninvoiced items needs to be kept uninvoiced in case of churn and reopen. """
        self.subscription_tmpl.plan_id = self.plan_year.id
        subscription = self.env['sale.order'].create({
            'name': 'Parent Sub',
            'is_subscription': True,
            'note': "original subscription description",
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
            'start_date': '2025-01-01',
        })
        self.flush_tracking()
        subscription.write({'order_line': [(0, 0, {
            'name': 'TestRecurringLine',
        'product_id': self.product.id,
            'product_uom_qty': 1,
        })]})

        subscription.action_confirm()
        self.flush_tracking()
        log1 = subscription.order_log_ids
        self.assertFalse(log1.effective_date)
        subscription._create_invoices()._post()
        self.flush_tracking() # make sure to launch _update_effective_date
        self.assertEqual(log1.effective_date, datetime.date(2025, 1, 1))

        # Test upselling with after a manual change
        order_line = subscription.order_line
        order_line.product_uom_qty = 2
        self.flush_tracking()
        log2 = subscription.order_log_ids[-1]
        self.assertFalse(log2.effective_date)

        action = subscription.prepare_upsell_order()
        upsell_so = self.env['sale.order'].browse(action['res_id'])
        upsell_so.start_date = '2025-04-01'
        upsell_so.order_line[0].product_uom_qty = 2
        upsell_so.action_confirm()
        self.flush_tracking()
        log3 = subscription.order_log_ids[-1]
        self.assertEqual(round(log3.amount_signed, 2), 16.66)
        self.assertFalse(log3.effective_date)
        upsell_so._create_invoices()._post()
        self.flush_tracking() # make sure to launch _update_effective_date
        self.assertFalse(log2.effective_date)
        self.assertEqual(log3.effective_date, datetime.date(2025, 4, 1))

        # Test churn and reopen
        subscription.set_close()
        self.flush_tracking()
        log4 = subscription.order_log_ids[-1]
        self.assertEqual(log2.effective_date, log4.effective_date)
        self.assertEqual(log4.effective_date, subscription.next_invoice_date)
        self.assertEqual(round(log4.amount_signed, 2), -33.33)

        subscription.set_open()
        self.flush_tracking()
        self.assertFalse(log4.exists())
        self.assertFalse(log2.effective_date)
        self.assertEqual(log3.effective_date, datetime.date(2025, 4, 1))
        self.assertEqual(log1.effective_date, datetime.date(2025, 1, 1))

        # Test renewal and cancel
        res = subscription.prepare_renewal_order()
        renewal_order = self.env['sale.order'].browse(res['res_id'])
        self.flush_tracking()
        renewal_order.action_confirm()
        self.flush_tracking()
        log5 = subscription.order_log_ids[-1]
        self.assertEqual(log2.effective_date, log5.effective_date)
        self.assertEqual(log5.effective_date, subscription.next_invoice_date)
        self.assertEqual(round(log5.amount_signed, 2), -33.33)

        renewal_order._action_cancel()
        self.flush_tracking()
        self.assertFalse(log5.exists())
        self.assertFalse(log2.effective_date)
        self.assertEqual(log3.effective_date, datetime.date(2025, 4, 1))
        self.assertEqual(log1.effective_date, datetime.date(2025, 1, 1))

    def test_is_closing(self):
        """
        Test subscription to ensure is_closing is set correctly based on
        subscription state, recurring invoices, and user-closing options.
        """
        with freeze_time("2024-07-30"):
            # Confirm subscription and generate an recurring invoice
            subscription = self.subscription
            subscription.action_confirm()
            subscription._create_recurring_invoice()
            self.assertFalse(subscription.is_closing, "Subscription should not be marked for closure upon confirmation.")
            self.assertEqual(subscription.subscription_state, '3_progress', "Subscription state should be 'in progress'.")

            subscription.plan_id.user_closable = True
            subscription.plan_id.user_closable_options = 'end_of_period'
            subscription.with_context(allow_future_end_date=True).set_close()
            # Verify that the subscription is now marked for closure
            self.assertTrue(subscription.is_closing, "Subscription should be marked for closure.")

        with freeze_time("2024-08-30"):
            self.env['sale.order']._cron_subscription_expiration()

            # Validate that the subscription is closed and is not marked for closure
            self.assertFalse(subscription.is_closing, "Subscription should not be marked for closure after churn.")
            self.assertEqual(subscription.subscription_state, '6_churn', "Subscription state should be 'churn'.")

    def test_invoice_credit_email_template(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_line_ids': [(0, 0, {
                'name': 'Test',
                'quantity': 1,
                'price_unit': 100,
                'subscription_id': self.subscription.id,
            })],
        })
        template_invoice_id = self.env['account.move.send']._get_default_mail_template_id(invoice).id
        self.assertEqual(template_invoice_id, self.env.ref('account.email_template_edi_invoice').id, 'The email template id for an Invoice is not what it should be.')
        credit_note = self.env['account.move'].create({
            'move_type': 'out_refund',
            'invoice_line_ids': [(0, 0, {
                'name': 'Test',
                'quantity': 1,
                'price_unit': 100,
                'subscription_id': self.subscription.id,
            })],
        })
        template_credit_id = self.env['account.move.send']._get_default_mail_template_id(credit_note).id
        self.assertEqual(template_credit_id, self.env.ref('account.email_template_edi_credit_note').id, 'The email template id for a Credit Note is not what it should be.')

    def test_next_billing_details(self):
        with freeze_time("2024-11-20"):
            """Test the value displayed on the portal"""
            mxn_currency = self._enable_currency('MXN')
            mxn_pricelist = self.env['product.pricelist'].create({
                'name': 'MXN pricelist',
                'currency_id': mxn_currency.id,
                'item_ids': [
                    Command.create({
                        'plan_id': self.plan_month.id,
                        'fixed_price': 6,
                        'product_tmpl_id': self.product.product_tmpl_id.id,
                    }),
                    Command.create({
                        'plan_id': self.plan_month.id,
                        'fixed_price': 600,
                        'product_tmpl_id': self.product2.product_tmpl_id.id,
                    }),
                ]
            })
            self.subscription.order_line[0].name = "First recurring product"
            self.subscription.order_line[1].name = "Second recurring product"
            self.product5.recurring_invoice = False
            self.subscription.order_line = [Command.create({
                'name': "Non recurring line",
                'product_id': self.product5.id, # non recurring product
                'product_uom_qty': 1
            })]
            self.subscription.action_confirm()
            details = self.subscription._next_billing_details()
            self.assertEqual(details["sale_order"], self.subscription, "self is the subscription")
            self.assertAlmostEqual(details["next_invoice_amount"], 69.3, 2, "The next invoice amount the total amount")
            self.subscription._create_recurring_invoice()
            details = self.subscription._next_billing_details()
            self.assertAlmostEqual(details["next_invoice_amount"], 23.1, 2, "Only the recurring product is invoiced")
        with freeze_time("2024-12-20"):
            action = self.subscription.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so.pricelist_id = mxn_pricelist
            renewal_so.order_line = [Command.create({
                'name': "Non recurring line",
                'product_id': self.product5.id, # non recurring product
                'product_uom_qty': 2
            })]
            renewal_so.action_update_prices()
            renewal_so.action_confirm()
            details = renewal_so._next_billing_details()
            self.assertAlmostEqual(details["next_invoice_amount"], 759.0, 2, "Only the recurring product is invoiced")
            inv = renewal_so._create_recurring_invoice()
            details = renewal_so._next_billing_details()
            self.assertAlmostEqual(details["next_invoice_amount"], 666.6, 2, "Only the recurring product is invoiced")

    def test_postpaid_next_invoice_date(self):
        """" Ensure the next invoice date is correctly updated for postpaid orders
        This test fix a bug where a new invoice was created every day if postpaid line were mixed with non recurring lines
        """
        # FIXME ARJ, should be an at_install test
        if self.env.ref('base.module_sale_subscription_stock').state == 'installed':
            self.skipTest("`stock` module is installed. The invoice amount depends on the stock.move validation")
        with freeze_time("2025-01-01"):
            sub_product_delivery = self.env['product.product'].create({
                'name': "Subscription consumable invoiced on delivery",
                'list_price': 42,
                'type': 'consu',
                'uom_id': self.uom_unit.id,
                'invoice_policy': 'delivery',
                'recurring_invoice': True,
            })
            product_non_recurring = self.env['product.product'].create({
                'name': "Consumable invoiced on order",
                'list_price': 30.0,
                'type': 'consu',
                'uom_id': self.uom_unit.id,
                'invoice_policy': 'order',
            })
            sub = self.env['sale.order'].create({
                'name': 'Delivery',
                'is_subscription': True,
                'partner_id': self.user_portal.partner_id.id,
                'plan_id': self.plan_month.id,
                'pricelist_id': self.pricelist.id,
                'order_line': [Command.create({
                    'product_id': sub_product_delivery.id,
                    'product_uom_qty': 1,
                    'tax_ids': [Command.clear()],
                }), Command.create({
                    'product_id': product_non_recurring.id,
                    'product_uom_qty': 1,
                    'tax_ids': [Command.clear()],
                })],
            })
            sub.action_confirm()
            inv = sub._create_recurring_invoice()
            self.assertEqual(sub.next_invoice_date, datetime.date(2025, 2, 1))
            self.assertAlmostEqual(inv.amount_untaxed, 30, msg="We invoice only the non recurring product")
            recurring_line = sub.order_line.filtered(lambda l: l.product_id.id == sub_product_delivery.id)
            recurring_line.qty_delivered = 1

        with freeze_time("2025-02-01"):
            inv = self.env['sale.order']._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 42, msg="We invoice recurring products")
            self.assertEqual(sub.next_invoice_date, datetime.date(2025, 3, 1))

        with freeze_time("2025-03-01"):
            inv = sub._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 42, msg="We invoice recurring products")
            self.assertEqual(sub.next_invoice_date, datetime.date(2025, 4, 1))

    def test_compute_unit_price_second_upsell(self):
        # Make sure upselling twice the same order don't reset the parent_line_id
        delivered_product_tmpl = self.env['product.template'].create({
            'name': 'Delivery product',
            'type': 'consu',
            'recurring_invoice': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'invoice_policy': 'order',
            'list_price': 50.0,
        })
        product = delivered_product_tmpl.product_variant_id
        # create a subscription with a custom price_unit
        subscription = self.env['sale.order'].create({
            'name': 'Original subscription',
            'is_subscription': True,
            'partner_id': self.partner.id,
            'plan_id': self.plan_month.id,
            'order_line': [
                Command.create({
                    'name': product.name,
                    'product_id': product.id,
                    'product_uom_qty': 1,
                    'product_uom_id': self.env.ref('uom.product_uom_unit').id,
                    'price_unit': 10,
                }),
            ]
        })

        subscription.action_confirm()
        move = subscription._create_invoices()
        move.action_post()
        # Create two upsells and confirm them later.
        action = subscription.prepare_upsell_order()
        upsell = self.env['sale.order'].browse(action['res_id'])
        upsell.name = "UPSELL 1"
        action2 = subscription.prepare_upsell_order()
        upsell2 = self.env['sale.order'].browse(action2['res_id'])
        upsell2.name = "UPSELL 2"
        self.assertEqual(upsell.order_line.parent_line_id, subscription.order_line, "The parent_line_id should be correctly set")
        self.assertEqual(upsell2.order_line.parent_line_id, subscription.order_line, "The parent_line_id should be correctly set")
        # upsell confirmation
        upsell.action_confirm()
        self.assertEqual(upsell.order_line.price_unit, 10, "The unit price should be the same as the original subscription")
        self.assertEqual(upsell.order_line.parent_line_id, subscription.order_line, "The parent_line_id should be correctly set")
        self.assertEqual(upsell2.order_line.price_unit, 10, "The unit price should be the same as the original subscription")
        self.assertEqual(upsell2.order_line.parent_line_id, subscription.order_line, "The unit price should be the same as the original subscription")

        upsell2.action_confirm()
        self.assertEqual(upsell2.order_line.price_unit, 10, "The unit price should be the same as the original subscription")
        self.assertEqual(upsell.order_line.parent_line_id, subscription.order_line, "The parent_line_id of first upsell should not be reset")
        self.assertEqual(upsell.order_line.price_unit, 10, "The unit price shouldn't get updated")

    def test_not_override_end_date_in_expiration_cron(self):
        """Ensure the expiration cron does not override an existing past end_date."""
        with freeze_time("2025-05-05"):
            self.subscription.write({'end_date': datetime.date(2025, 6, 4)})
            self.subscription.action_confirm()
            self.subscription._create_recurring_invoice()
            today = fields.Date.today()
            self.assertEqual(self.subscription.start_date, today, "start date set to today")
            self.assertEqual(self.subscription.next_invoice_date, datetime.date(2025, 6, 5))
            self.assertEqual(self.subscription.end_date, datetime.date(2025, 6, 4))

        with freeze_time("2025-06-10"):
            self.env["sale.order"].sudo()._cron_subscription_expiration()
            self.assertEqual(self.subscription.end_date, datetime.date(2025, 6, 4), "after expiration cron run, end_date should remain unchanged if already set and in the past")

    def test_null_ordered_quantity(self):
        """ Null recurring line should not appear in the invoice """
        with freeze_time("2025-06-03"):
            self.assertEqual(self.product3.invoice_policy, 'order', "We need invoice policy order for this test")
            self.subscription.order_line = [Command.create({
                    'name': self.product3.name,
                    'product_id': self.product3.id,
                    'product_uom_qty': 0,
                    'product_uom_id': self.env.ref('uom.product_uom_unit').id,
                    'price_unit': 10,

            })]
            self.subscription.action_confirm()
            inv = self.subscription._cron_recurring_create_invoice()
            self.assertEqual(len(inv.invoice_line_ids), 2)
            product_ids = inv.invoice_line_ids.product_id
            self.assertEqual(len(product_ids), 2)
            self.assertTrue(self.product.id in product_ids.ids)
            self.assertTrue(self.product2.id in product_ids.ids)

    def test_upsell_invoice_line_description(self):
        self.plan_year.billing_first_day = True
        with freeze_time("06/30/2025"):
            subscription = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'plan_id': self.plan_year.id,
                'order_line': [
                    Command.create({
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 2.0,
                        'product_uom_id': self.product.uom_id.id,
                        'price_unit': 12,
                        })],
            })
            subscription.plan_id = self.plan_year
            subscription.action_confirm()
            subscription._cron_recurring_create_invoice()
            invoice = subscription._create_invoices()
            invoice.action_post()
            action = subscription.prepare_upsell_order()
            upsell = self.env['sale.order'].browse(action['res_id'])
            upsell.action_confirm()
            line = upsell.order_line[0]._prepare_invoice_line()

            self.assertIn("550 days 06/30/2025 to 12/31/2026", line['name'])

    def test_subscription_upsell_alternative_invoice(self):
        self.subscription.action_confirm()
        self.env['sale.order']._cron_recurring_create_invoice()
        action = self.subscription.prepare_upsell_order()
        upsell_so = self.env['sale.order'].browse(action['res_id'])
        action = upsell_so.create_alternative()
        alternative_upsell_so = self.env['sale.order'].browse(action['res_id'])
        alternative_upsell_order_line = alternative_upsell_so.order_line.filtered(lambda line: not line.display_type)
        for sol in alternative_upsell_order_line:
            sol.product_uom_qty = 1.0
        alternative_upsell_so.action_confirm()
        alternative_upsell_so._create_invoices()
        self.assertTrue(len(alternative_upsell_so.invoice_ids), "An invoice should have been created for the alternative upsell sale order.")

    def test_churn_discount_removal(self):
        """ Test the following flow:
                Sub with first year discount -> Renew -> Discount is removed on original sub -> Cancel the renewal -> Churn the original sub
            This flow was causing an issue where the churn log amount was set as the full amount instead of the discounted amount which resulted negative MRR.
        """
        # create new subscription with discount
        self.product2.list_price = -1
        sub = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'plan_id': self.plan_year.id,
            'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 10.0,
                    }),
                    (0, 0, {
                        'name': self.product2.name,
                        'product_id': self.product2.id,
                        'product_uom_qty': 1.0,
                    }),
                ],
        })
        self.flush_tracking()
        sub.action_confirm()
        self.flush_tracking()
        new_log = sub.order_log_ids
        self.assertEqual([new_log.event_type, new_log.amount_signed], ['0_creation', 83.25])
        sub._create_recurring_invoice()

        # renew the subscription without discount
        action = sub.prepare_renewal_order()
        renewal_so = self.env['sale.order'].browse(action['res_id'])
        renewal_so.order_line.filtered(lambda l: l.product_id == self.product2).unlink()
        self.flush_tracking()
        renewal_so.action_confirm()
        self.flush_tracking()

        # remove first year discount on original subscription
        # shoudln't be doable normally but this simulate first year discount removal via cron
        sub.order_line.filtered(lambda l: l.product_id == self.product2).unlink()

        # cancel renewal
        self.flush_tracking()
        renewal_so._action_cancel()
        self.flush_tracking()

        # churn
        sub.set_close()
        self.flush_tracking()
        self.assertEqual(sum(sub.order_log_ids.mapped('amount_signed')), 0)

    def test_subscription_discount_on_non_sub_lines(self):
        """
        Check that discounts manually set on non-subscription order lines are preserved after creating
        the subscription and when closing it.
        """
        DISCOUNT_10 = 10
        self.product2.recurring_invoice = False

        subscription = self.env['sale.order'].create({
            'name': 'Test subscription',
            'is_subscription': True,
            'partner_id': self.partner.id,
            'plan_id': self.plan_month.id,
            'order_line': [
                Command.create({
                    'name': 'Subscription product',
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'discount': DISCOUNT_10,
                }),
                Command.create({
                    'name': 'Non-subscription product',
                    'product_id': self.product2.id,
                    'product_uom_qty': 1,
                    'discount': DISCOUNT_10,
                })
            ]
        })

        self.assertEqual(subscription.order_line.mapped("discount"), [DISCOUNT_10, DISCOUNT_10])

        subscription.action_confirm()
        subscription._cron_recurring_create_invoice()
        subscription.set_close()

        self.assertEqual(subscription.order_line.mapped("discount"), [DISCOUNT_10, DISCOUNT_10])

    def test_proper_effective_date(self):
        """ Make sure that the effective date is correct when the order is confirmed
        and the first account.move are performed in the same transaction
        (no flush between confirm and _post).
        This flow can be done by paying/confirming a SO on the portal.
        """
        self.subscription_tmpl.plan_id = self.plan_year.id
        subscription = self.env['sale.order'].create({
            'name': 'Parent Sub',
            'is_subscription': True,
            'note': "original subscription description",
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
            'start_date': '2025-01-01',
            'order_line': [(0, 0, {
                'name': 'TestRecurringLine',
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        self.flush_tracking()
        subscription.action_confirm()
        log = subscription.order_log_ids
        self.assertFalse(log.effective_date)
        inv = subscription._create_invoices()
        inv._post()
        self.flush_tracking()
        log = subscription.order_log_ids
        self.assertEqual(log.effective_date, datetime.date(2025, 1, 1))
        # Simulate a new transaction, without flush after précommit
        self.env.invalidate_all(flush=False)
        self.assertEqual(log.effective_date, datetime.date(2025, 1, 1))

    def test_product_subscription_pricing_copy(self):
        """Check that product variants on product pricings after copying
        a product template.
        """
        product = self.product_tmpl_2
        product_attribute = self.env['product.attribute'].create({
            'name': 'Color',
            'value_ids': [Command.create({'name': name}) for name in ('Blue', 'Red')],
        })
        product.attribute_line_ids = 2 * [Command.create({
            'attribute_id': product_attribute.id,
            'value_ids': product_attribute.value_ids.ids,
        })]
        for i, variant in enumerate(product.product_variant_ids, start=1):
            self.env['product.pricelist.item'].create([{
                'product_tmpl_id': product.id,
                'product_id': variant.id,
                'plan_id': self.plan_week.id,
                'fixed_price': 10.0 * i,
            }, {
                'product_tmpl_id': product.id,
                'product_id': variant.id,
                'plan_id': self.plan_month.id,
                'fixed_price': 25.0 * i,
           }])
        pricings_1 = product.subscription_rule_ids
        pricings_2 = product.copy().subscription_rule_ids
        self.assertEqual(
            len(pricings_2),
            8,  # 2 attributes * 2 values * 2 plans = 8 pricings
            "copied product should get 8 pricings",
        )
        self.assertNotEqual(
            pricings_2.product_id,
            pricings_1.product_id,
            "copied pricings shouldn't be linked to the original products",
        )
        for pricing_1, pricing_2 in zip(pricings_1, pricings_2, strict=True):
            self.assertEqual(pricing_2.fixed_price, pricing_1.fixed_price)
            self.assertEqual(pricing_2.plan_id, pricing_1.plan_id)
            self.assertEqual(pricing_2.pricelist_id, pricing_1.pricelist_id)

    def test_renew_subscription_keeps_non_empty_sections_and_notes(self):
        self.subscription_tmpl.plan_id = self.plan_year.id
        sub_1 = self.env['sale.order'].create({
            'name': 'Parent Sub',
            'is_subscription': True,
            'note': "original subscription description",
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
            'start_date': '2025-01-01',
            'order_line': [
                (0, 0, {
                    'name': 'Section 1',
                    'display_type': 'line_section'
                }),
                (0, 0, {
                    'name': 'TestRecurringLine',
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                }),
                (0, 0, {
                    'name': 'Some note',
                    'display_type': 'line_note'
                }),
                (0, 0, {
                    'name': 'Section 2',
                    'display_type': 'line_section'
                }),
            ],
        })

        self.assertEqual(4, len(sub_1.order_line))
        sub_1.action_confirm()
        sub_1._create_recurring_invoice()
        action = sub_1.prepare_renewal_order()
        renewal_so = self.env['sale.order'].browse(action['res_id'])
        self.assertEqual(3, len(renewal_so.order_line))
        self.assertTrue(renewal_so.order_line.search([('order_id', '=', renewal_so.id), ('name', '=', 'Section 1')]))
        self.assertTrue(renewal_so.order_line.search([('order_id', '=', renewal_so.id), ('name', '=', 'TestRecurringLine')]))
        self.assertTrue(renewal_so.order_line.search([('order_id', '=', renewal_so.id), ('name', '=', 'Some note')]))
        self.assertFalse(renewal_so.order_line.search([('order_id', '=', renewal_so.id), ('name', '=', 'Section 2')]))

    def test_subscription_product_update_on_parent_line_in_upsell(self):
        """
        Check recurring product quantity on subscription after updating product
        on parent line in upsell and confirm.
        """
        # Non-recurring product
        nr_product = self.env['product.product'].create({
            'name': 'Non recurring product',
            'type': 'service',
            'uom_id': self.product.uom_id.id,
            'list_price': 25,
        })
        # Subscription
        subscription = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'company_id': self.company_data['company'].id,
            'plan_id': self.plan_month.id,
            'order_line': [
                Command.create({
                    'product_id': self.product.id,
                    'product_uom_qty': 2.0,
                    'price_unit': 12,
                })
            ],
        })
        subscription.action_confirm()
        sub_line = subscription.order_line
        self.assertEqual(len(sub_line), 1)
        self.assertEqual(sub_line.product_uom_qty, 2.0)
        self.env['sale.order']._cron_recurring_create_invoice()

        # Upsell
        action = subscription.prepare_upsell_order()
        upsell_so = self.env['sale.order'].browse(action['res_id'])
        self.assertEqual(subscription.order_line, upsell_so.order_line.parent_line_id,
                         "The parent line is the one from the subscription")
        upsell_order_line = upsell_so.order_line.filtered(lambda line: not line.display_type)
        self.assertEqual(upsell_order_line.product_uom_qty, 0.0, 'The upsell order has 0 quantity')

        # Update the existing line with non-recurring product and quantity
        upsell_order_line.product_id = nr_product
        upsell_order_line.product_uom_qty = 11.0

        # Confirm upsell
        upsell_so._confirm_upsell()
        upsell_line = upsell_so.order_line.filtered(lambda line: not line.display_type)
        self.assertEqual(len(upsell_line), 1)
        self.assertFalse(upsell_line.parent_line_id)
        self.assertEqual(upsell_line.product_uom_qty, 11.0)
        # Check recurring product quantity after upsell
        self.assertEqual(len(subscription.order_line), 1)
        self.assertEqual(subscription.order_line.product_uom_qty, 2.0,
                         "The recurring product's quantity should not be changed in subscription")

    def test_partial_refund_reduces_invoiced_quantity_on_subscription(self):
        """
        Verify that a partial refund on a subscription invoice
        correctly updates the invoiced quantity on the order line.
        """
        with freeze_time("2024-09-01"):
            subscription = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    (0, 0, {
                        'name': self.product.name,
                        'product_id': self.product.id,
                        'product_uom_qty': 3.0,
                        'product_uom_id': self.product.uom_id.id,
                        'price_unit': 12,
                    })],
            })
            subscription.action_confirm()
            subscription._create_recurring_invoice()
            self.assertEqual(subscription.order_line.qty_invoiced, 3, "The 3 products should be invoiced")
            subscription._get_invoiced()
            inv = subscription.invoice_ids
            inv.payment_state = 'paid'
            refund_wizard = self.env['account.move.reversal'].with_context(
                active_model="account.move",
                active_ids=inv.ids).create({
                'reason': 'Partial refund for Product A',
                'journal_id': inv.journal_id.id,
            })
            refund_wizard.reverse_moves()

            credit_note = self.env['account.move'].search([
                ('reversed_entry_id', '=', inv.id),
                ('move_type', '=', 'out_refund'),
            ], limit=1)

            for line in credit_note.invoice_line_ids:
                if line.product_id.id == self.product.id:
                    line.quantity = 2

            credit_note._compute_amount()
            credit_note._compute_tax_totals()

            credit_note.action_post()

        self.assertEqual(subscription.order_line.qty_invoiced, 1,
                         "The invoiced quantity should be reduced by the refund")

    def test_sale_subscription_optional_product_discount(self):
        """
        Check that the discount on an optional product is correctly applied when the option is added to a SO.
        """
        subscription = self.env['sale.order'].create({
            'name': "Test subscription",
            'is_subscription': True,
            'partner_id': self.partner.id,
            'plan_id': self.plan_month.id,
            'order_line': [
                Command.create({
                    'name': "Subscription product",
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                }),
                Command.create({
                    'name': "Optional products",
                    'display_type': 'line_section',
                    'is_optional': True,
                }),
                Command.create({
                    'product_id': self.product2.id,
                    'discount': 20,  # 20% discount
                })
            ],
        })

        self.assertEqual(subscription.order_line.mapped("discount"), [0, 0, 20])

    def test_correct_functioning_of_proration(self):
        """
        Check that the behavior of the allow_prorated_price flag is correct
        """

        with freeze_time("2025-08-19"):

            # Case 1: Service product with default flag (on)

            product_tmpl1 = self.ProductTmpl.create({
                'name': 'Prorated Service Product',
                'type': 'service',
                'recurring_invoice': True,
                'invoice_policy': 'order',
            })
            sale_order = self.env['sale.order'].create({
                'name': 'Test Sale Order',
                'partner_id': self.partner_a.id,
                'plan_id': self.plan_month.id,
                'order_line': [Command.create({
                        'product_id': product_tmpl1.product_variant_id.id,
                        'product_uom_qty': 1,
                        'price_unit': 10})]
                })
            sale_order.plan_id.billing_first_day = True
            sale_order.action_confirm()
            inv = sale_order._create_recurring_invoice()
            self.assertEqual(inv.amount_untaxed, 4.19, "The invoiced amount should be 4.19 because the product is a default service and should be prorated.")
            self.assertTrue(product_tmpl1.allow_prorated_price, "The product is a default service, therefore it should be prorated.")

            # Case 2: Service product with flag turned off

            product_tmpl2 = self.ProductTmpl.create({
                'name': 'Non Prorated Service Product',
                'type': 'service',
                'recurring_invoice': True,
                'invoice_policy': 'order',
            })
            product_tmpl2.write({'allow_prorated_price': False})

            sale_order = self.env['sale.order'].create({
                'name': 'Test Sale Order',
                'partner_id': self.partner_a.id,
                'plan_id': self.plan_month.id,
                'order_line': [Command.create({
                        'product_id': product_tmpl2.product_variant_id.id,
                        'product_uom_qty': 1,
                        'price_unit': 10})]
                })

            sale_order.plan_id.billing_first_day = True
            sale_order.action_confirm()
            inv = sale_order._create_recurring_invoice()
            self.assertEqual(inv.amount_untaxed, 10, "The invoiced amount should be 10 because the product is a service with the proration manually turned off.")

            # Case 3: Good product with default flag (off)

            product_tmpl3 = self.ProductTmpl.create({
                'name': 'Good Product',
                'type': 'consu',
                'recurring_invoice': True,
                'invoice_policy': 'order',
            })

            sale_order = self.env['sale.order'].create({
                'name': 'Test Sale Order',
                'partner_id': self.partner_a.id,
                'plan_id': self.plan_month.id,
                'order_line': [Command.create({
                        'product_id': product_tmpl3.product_variant_id.id,
                        'product_uom_qty': 1,
                        'price_unit': 10})]
                })

            sale_order.plan_id.billing_first_day = True
            sale_order.action_confirm()
            inv = sale_order._create_recurring_invoice()
            self.assertEqual(inv.amount_untaxed, 10, "The invoiced amount should be 10 because the product is a good, which means it has proration off by default.")
            self.assertFalse(product_tmpl3.allow_prorated_price, "The product is a good, so by default it should not be prorated.")

            # Case 4: Service product invoiced on delivery with default flag (off)
            product_tmpl4 = self.ProductTmpl.create({
                'name': 'Service Product Invoiced On Delivery',
                'type': 'service',
                'recurring_invoice': True,
                'invoice_policy': 'delivery',
            })

            sale_order = self.env['sale.order'].create({
                'name': 'Test Sale Order',
                'partner_id': self.partner_a.id,
                'plan_id': self.plan_month.id,
                'order_line': [Command.create({
                        'product_id': product_tmpl4.product_variant_id.id,
                        'product_uom_qty': 1,
                        'price_unit': 10})]
                })

            sale_order.plan_id.billing_first_day = True
            sale_order.action_confirm()
            inv = sale_order._create_recurring_invoice()
            self.assertEqual(inv.amount_untaxed, 0, "The invoiced amount should be 0 because the product is billed on delivery and nothing has been delivered.")
            self.assertFalse(product_tmpl4.allow_prorated_price, "The product is invoiced based on delivery, therefore it should not be prorated.")

            # Case 5: Non recurring product (flag off by default) + Recurring Service (flag on by default)
            product_tmpl5 = self.ProductTmpl.create({
                'name': 'Non Recurring Product',
                'type': 'service',
                'recurring_invoice': False,
                'invoice_policy': 'order',
            })

            sale_order = self.env['sale.order'].create({
                'name': 'Test Sale Order',
                'partner_id': self.partner_a.id,
                'plan_id': self.plan_month.id,
                'order_line': [
                    Command.create({
                        'product_id': product_tmpl5.product_variant_id.id,
                        'product_uom_qty': 1,
                        'price_unit': 10}),
                    Command.create({
                        'product_id': product_tmpl1.product_variant_id.id,
                        'product_uom_qty': 1,
                        'price_unit': 10})]
                })

            sale_order.plan_id.billing_first_day = True
            sale_order.action_confirm()
            inv = sale_order._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 14.19, msg="The invoiced amount should be 14.19 because the recurring service should be prorated and the non recurring one shouldn't.")
            self.assertFalse(product_tmpl5.allow_prorated_price, "The product is not a subscription, so it should not be prorated.")

    @freeze_time('2025-09-15')
    def test_postpaid_first_day(self):
        """ Ensure the behavior is correct when all lines are postpaid and the contracts are aligned on first day of the month """
        product_tmpl1 = self.ProductTmpl.create({
                'name': 'Prorated Service Product',
                'type': 'service',
                'recurring_invoice': True,
                'invoice_policy': 'delivery',
        })
        product_tmpl2 = product_tmpl1.copy()

        sale_order = self.env['sale.order'].create({
            'name': 'Test Sale Order',
            'partner_id': self.partner_a.id,
            'plan_id': self.plan_month.id,
            'order_line': [Command.create({
                    'product_id': product_tmpl1.product_variant_id.id,
                    'product_uom_qty': 1,
                    'price_unit': 10}),
                    Command.create({
                    'product_id': product_tmpl2.product_variant_id.id,
                    'product_uom_qty': 1,
                    'price_unit': 20})]
        })
        sale_order.plan_id.billing_first_day = True
        sale_order.action_confirm()
        self.assertEqual(sale_order.next_invoice_date, datetime.date(2025, 10, 1), "The next invoice date is first of october")

    def test_invoice_after_deleting_invoiced_line(self):
        """ Test that invoicing works correctly after deleting an already invoiced subscription line.
        This test covers the fix for _get_max_invoiced_date when sale_line_ids is empty
        """
        product_a = self.env['product.product'].create({
            'name': 'Car Leasing (SUB)',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'list_price': 20,
        })
        product_b = self.env['product.product'].create({
            'name': 'Office Cleaning Service (SUB)',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'list_price': 10,
        })

        with freeze_time('2025-11-11'):
            subscription = self.env['sale.order'].create({
                'name': 'Test Subscription',
                'is_subscription': True,
                'plan_id': self.plan_month.id,
                'partner_id': self.partner.id,
                'order_line': [Command.create({
                    'product_id': product_a.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 20,
                })],
            })
            subscription.action_confirm()

            invoice_1 = subscription._create_invoices()
            invoice_1._post()

            self.assertEqual(len(subscription.invoice_ids), 1, 'First invoice should be created')
            self.assertEqual(subscription.order_line.qty_invoiced, 1.0, 'Product A should be invoiced')

            subscription.write({
                'order_line': [Command.create({
                    'product_id': product_b.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 10,
                })],
            })

            line_to_delete = subscription.order_line.filtered(lambda l: l.product_id == product_a)
            line_to_delete.unlink()

            self.assertEqual(len(subscription.order_line), 1, 'Only product B line should remain')
            self.assertEqual(subscription.order_line.product_id, product_b, 'Remaining line should be product B')
            self.assertEqual(len(subscription.invoice_ids), 1, 'Invoice for product A should still exist')

            invoice_2 = subscription._create_invoices()

            self.assertTrue(invoice_2, 'Second invoice should be created successfully')
            self.assertEqual(len(subscription.invoice_ids), 2, 'Should have two invoices total')

            invoice_2_lines = invoice_2.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
            self.assertEqual(len(invoice_2_lines), 1, 'Second invoice should have one product line')
            self.assertEqual(invoice_2_lines.product_id, product_b, 'Second invoice should be for product B')

            invoice_2._post()
            self.assertEqual(invoice_2.state, 'posted', 'Second invoice should be posted successfully')
