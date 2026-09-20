from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon, EXTERNAL_MODE


@tagged('post_install_l10n', 'post_install', '-at_install', *(['-standard', 'external'] if EXTERNAL_MODE else []))
class TestCFDIInvoiceSale(TestMxEdiCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.write({'group_ids': [(4, cls.env.ref('sales_team.group_sale_salesman').id)]})

    def test_global_discount(self):
        product1 = self.product
        product2 = self._create_product()
        product3 = self._create_product()

        to_test = list(range(10, 16))
        with self.mx_external_setup(self.frozen_today):
            for percent in to_test:
                with self.subTest(percent=percent):
                    sale_order = self.env['sale.order'].create({
                        'partner_id': self.partner_mx.id,
                        'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_efectivo').id,
                        'order_line': [
                            Command.create({
                                'product_id': product1.id,
                                'price_unit': 6194.83,
                                'product_uom_qty': 10.0,
                            }),
                            Command.create({
                                'product_id': product2.id,
                                'price_unit': 7194.83,
                                'product_uom_qty': 5.0,
                            }),
                            Command.create({
                                'product_id': product3.id,
                                'price_unit': 8194.83,
                                'product_uom_qty': 1.0,
                            }),
                        ],
                    })
                    sale_order.action_confirm()
                    self.assertRecordValues(sale_order, [{
                        'amount_untaxed': 106117.28,
                        'amount_tax': 16978.76,
                        'amount_total': 123096.04,
                    }])

                    wizard = self.env['sale.order.discount'].create({
                        'sale_order_id': sale_order.id,
                        'discount_type': 'so_discount',
                        'discount_percentage': percent / 100.0,
                    })
                    wizard.action_apply_discount()

                    wizard = (
                        self.env['sale.advance.payment.inv']
                        .with_context({'active_model': sale_order._name, 'active_ids': sale_order.ids})
                        .create({
                            'advance_payment_method': 'delivered',
                            'amount': 0.0,
                            'fixed_amount': 0.0,
                        })
                    )
                    action_values = wizard.create_invoices()
                    invoice = self.env['account.move'].browse(action_values['res_id'])
                    invoice.action_post()
                    with self.with_mocked_pac_sign_success():
                        invoice._l10n_mx_edi_cfdi_invoice_try_send()
                    self._assert_invoice_cfdi(invoice, f"test_global_discount_{str(percent).replace('.', '_')}")

    def test_down_payment(self):
        to_test = list(range(10, 16))
        with self.mx_external_setup(self.frozen_today):
            for percent in to_test:
                with self.subTest(percent=percent):
                    sale_order = self.env['sale.order'].create({
                        'partner_id': self.partner_mx.id,
                        'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_efectivo').id,
                        'order_line': [
                            Command.create({
                                'product_id': self.product.id,
                                'price_unit': 6194.83,
                            }),
                        ],
                    })
                    sale_order.action_confirm()
                    self.assertRecordValues(sale_order, [{
                        'amount_untaxed': 6194.83,
                        'amount_tax': 991.17,
                        'amount_total': 7186.0,
                    }])

                    wizard = (
                        self.env['sale.advance.payment.inv']
                        .with_context({'active_model': sale_order._name, 'active_ids': sale_order.ids})
                        .create({
                            'advance_payment_method': 'percentage',
                            'amount': percent,
                        })
                    )
                    action_values = wizard.create_invoices()
                    invoice = self.env['account.move'].browse(action_values['res_id'])
                    invoice.action_post()
                    with self.with_mocked_pac_sign_success():
                        invoice._l10n_mx_edi_cfdi_invoice_try_send()
                    self._assert_invoice_cfdi(invoice, f"test_down_payment_{str(percent).replace('.', '_')}")

                    wizard = (
                        self.env['sale.advance.payment.inv']
                        .with_context({'active_model': sale_order._name, 'active_ids': sale_order.ids})
                        .create({
                            'advance_payment_method': 'delivered',
                            'amount': 0.0,
                            'fixed_amount': 0.0,
                        })
                    )
                    action_values = wizard.create_invoices()
                    invoice = self.env['account.move'].browse(action_values['res_id'])
                    invoice.action_post()
                    with self.with_mocked_pac_sign_success():
                        invoice._l10n_mx_edi_cfdi_invoice_try_send()
                    self._assert_invoice_cfdi(invoice, f"test_down_payment_{str(percent).replace('.', '_')}_final")
