# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.website_sale.tests.common import MockRequest, WebsiteSaleCommon
from odoo.addons.website_sale_external_tax.controllers.main import WebsiteSaleExternalTaxCalculation, WebsiteSaleDelivery
from odoo.addons.sale_external_tax.models.sale_order import SaleOrder as SaleOrderExternalTax


@tagged('post_install', '-at_install')
class TestWebsiteSaleExternalTaxCalculation(PaymentHttpCommon, WebsiteSaleCommon):

    def setUp(self):
        super().setUp()
        self.Controller = WebsiteSaleExternalTaxCalculation()

    def test_validate_payment_with_error_from_external_provider(self):
        """
        Payment should be blocked if external tax provider raises an error
        (invalid address, connection issue, etc ...)
        """
        with (
            patch(
                'odoo.addons.account_external_tax.models.account_external_tax_mixin.AccountExternalTaxMixin._get_external_taxes',
                side_effect=UserError('bim bam boom')
            ),
            MockRequest(self.env, website=self.website, sale_order_id=self.empty_cart.id),
            self.assertRaisesRegex(ValidationError, 'bim bam boom')
        ):
            self.Controller.shop_payment_validate()

    def test_order_summary_values_with_external_tax_error(self):
        """_order_summary_values should return external_tax_error if tax calc fails."""
        so = self.env['sale.order'].create({
            'website_id': self.website.id,
            'partner_id': self.env.user.partner_id.id,
            'order_line': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 5,
                'price_unit': self.product.list_price,
            })]
        })

        with MockRequest(self.env, website=self.website, sale_order_id=so.id) as req:
            order = req.cart

            with patch.object(
                SaleOrderExternalTax,
                '_get_and_set_external_taxes_on_eligible_records',
                side_effect=UserError("Simulated external tax failure")
            ):
                controller = WebsiteSaleDelivery()
                res = controller._order_summary_values(order)
                self.assertIn('external_tax_error', res)
                self.assertEqual(res['external_tax_error'], "Simulated external tax failure")
