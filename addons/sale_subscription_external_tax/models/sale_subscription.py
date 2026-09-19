# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _create_recurring_invoice(self, batch_size=30):
        invoices = super()._create_recurring_invoice(batch_size)
        # Already compute taxes for unvalidated documents as they can already be paid
        invoices._get_and_set_external_taxes_on_eligible_records()
        return invoices

    def _do_payment(self, payment_token, invoice, auto_commit=False):
        invoice._get_and_set_external_taxes_on_eligible_records()
        return super()._do_payment(payment_token, invoice, auto_commit=auto_commit)

    def _get_external_tax_service_params(self):
        params = super()._get_external_tax_service_params()
        if self.is_subscription:
            params['document_date'] = self.next_invoice_date or fields.Date.context_today(self)
        return params

    def _get_line_data_for_external_taxes(self):
        """EXTENDS 'account.external.tax.mixin'. Override to exclude non-invoicable lines. Only override for confirmed
        orders. Non-confirmed orders never have invoicable lines and can be paid through /my/orders which will ask to
        pay all lines. """
        res = super()._get_line_data_for_external_taxes()
        filtered_res = []

        for line in res:
            sale_line = line['base_line']['record']
            order = sale_line.order_id
            if order.is_subscription and order.state == 'sale':
                if sale_line in order._get_invoiceable_lines():
                    filtered_res.append(line)
            else:
                filtered_res.append(line)

        return filtered_res
