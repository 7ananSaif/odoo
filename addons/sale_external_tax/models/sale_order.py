# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['account.external.tax.mixin', 'sale.order']

    def action_confirm(self):
        """ Ensure confirmed orders have the right taxes. """
        self._get_and_set_external_taxes_on_eligible_records()
        return super().action_confirm()

    def action_quotation_send(self):
        """ Calculate taxes before presenting order to the customer. """
        self._get_and_set_external_taxes_on_eligible_records()
        return super().action_quotation_send()

    def _get_and_set_external_taxes_on_eligible_records(self):
        """ account.external.tax.mixin override. """
        eligible_orders = self.filtered(
            lambda order: order.is_tax_computed_externally and order.state in ('draft', 'sent', 'sale') and not order.locked
        )
        eligible_orders._set_external_taxes(eligible_orders._get_external_taxes())
        return super()._get_and_set_external_taxes_on_eligible_records()

    def _get_line_data_for_external_taxes(self):
        """ account.external.tax.mixin override. """
        AccountTax = self.env['account.tax']
        order_lines = self.order_line.filtered(lambda line: not line.display_type and not line.is_downpayment)
        base_lines = [line._prepare_base_line_for_taxes_computation() for line in order_lines]
        base_lines += self._add_base_lines_for_early_payment_discount()
        AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
        AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
        return [{'base_line': base_line, 'description': base_line['record'].name} for base_line in base_lines]
