# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.delivery_shiprocket.tests.common import ShiprocketCommon
from odoo.addons.payment_custom.tests.common import PaymentCustomCommon


@tagged('post_install', '-at_install')
class TestShiprocketPayment(PaymentCustomCommon, ShiprocketCommon):

    def test_when_shiprocket_cod_enabled_only_cod_pms_are_available(self):
        self.shiprocket.allow_cash_on_delivery = True
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'carrier_id': self.shiprocket.id,
        })
        compatible_providers = self.env['payment.provider'].sudo()._get_compatible_providers(
            self.company.id, self.partner.id, self.amount, sale_order_id=order.id
        )
        self.assertTrue(all(p.custom_mode == 'cash_on_delivery' for p in compatible_providers))
