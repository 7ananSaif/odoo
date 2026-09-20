# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models

from odoo.addons.payment import utils as payment_utils


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    @api.model
    def _get_compatible_providers(self, *args, sale_order_id=None, report=None, **kwargs):
        """ Override of payment to allow only COD providers if allow_cash_on_delivery is enabled for
        selected ups delivery method.
        :param int sale_order_id: The sales order to be paid, if any, as a `sale.order` id.
        :param dict report: The availability report.
        :return: The compatible providers.
        :rtype: payment.provider
        """
        compatible_providers = super()._get_compatible_providers(
            *args, sale_order_id=sale_order_id, report=report, **kwargs
        )

        sale_order = self.env['sale.order'].browse(sale_order_id).exists()
        if (
            sale_order.carrier_id.delivery_type == 'ups'
            and sale_order.carrier_id.allow_cash_on_delivery
        ):
            unfiltered_providers = compatible_providers
            compatible_providers = compatible_providers.filtered(
                lambda p: p.custom_mode == 'cash_on_delivery'
            )
            payment_utils.add_to_report(
                report,
                unfiltered_providers - compatible_providers,
                available=False,
                reason=_("UPS provider is configured to use only Collect on Delivery."),
            )

        return compatible_providers
