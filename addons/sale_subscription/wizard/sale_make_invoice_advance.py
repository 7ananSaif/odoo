# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import format_date


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    postpaid_warning_message = fields.Html(string='Warning Message', compute='_compute_postpaid_warning_message')

    @api.depends('sale_order_ids')
    def _compute_postpaid_warning_message(self):
        today = fields.Date.today()
        self.postpaid_warning_message = False
        for wiz in self:
            if not wiz.sale_order_ids:
                continue
            rendering_values = {'order_count': 0}
            for order in wiz.sale_order_ids:
                if not order.is_subscription:
                    continue
                if any(
                    line._is_postpaid_line()
                    and today < order.next_invoice_date
                    for line in order.order_line
                ):
                    if len(self.sale_order_ids) > 1:
                        rendering_values['order_count'] += len(self.sale_order_ids)
                        continue
                    else:
                        rendering_values['order_count'] += 1
                        product_list = []
                        for line in order.order_line:
                            if line._is_postpaid_line():
                                product_list.append(line.product_id.display_name)
                        rendering_values.update({
                            'next_invoice_date': format_date(self.env, order.next_invoice_date),
                             "product_list": product_list,
                        })
            wiz.postpaid_warning_message = self.env['ir.qweb']._render('sale_subscription.invoice_warning_message', {'rendering_values': rendering_values})

    def _create_invoices(self, sale_orders):

        if self.advance_payment_method != 'delivered':
            return super(SaleAdvancePaymentInv, self)._create_invoices(sale_orders)

        else:

            subscriptions = sale_orders.filtered('is_subscription')

            if subscriptions:
                # Close ending subscriptions
                auto_close_subscription = subscriptions.filtered_domain([('end_date', '!=', False)])
                auto_close_subscription._subscription_auto_close()

                # Set quantity to invoice before the invoice creation. If something goes wrong, the line will appear as "to invoice"
                subscription_invoiceable_lines = subscriptions._get_invoiceable_lines()
                subscription_invoiceable_lines._reset_subscription_qty_to_invoice()

            invoices = super(SaleAdvancePaymentInv, self)._create_invoices(sale_orders)

            if subscriptions:
                subscriptions._process_invoices_to_send(invoices)

            return invoices
