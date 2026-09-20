# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api
from odoo.fields import Domain
from odoo.tools import groupby


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _is_postpaid_line(self):
        self.ensure_one()
        return (self.product_id.service_policy == 'delivered_timesheet' and self.qty_delivered_method == 'timesheet') or super()._is_postpaid_line()

    def _get_timesheet_subscription_lines(self):
        return self.filtered(lambda sol: sol.recurring_invoice and sol.qty_delivered_method == 'timesheet')

    @api.depends('timesheet_ids', 'next_invoice_date')
    def _compute_qty_delivered(self):
        super()._compute_qty_delivered()

    def _prepare_qty_delivered(self):
        timesheet_lines = self._get_timesheet_subscription_lines()
        delivered_qties = super(SaleOrderLine, self - timesheet_lines)._prepare_qty_delivered()

        for so, lines in groupby(timesheet_lines, lambda sol: (sol.order_id)):
            lines_by_timesheet = sum(lines, self.env['sale.order.line'])
            domain = Domain(lines_by_timesheet._timesheet_compute_delivered_quantity_domain())
            refund_account_moves = so.invoice_ids.filtered(
                lambda am: am.state == 'posted' and am.move_type == 'out_refund').reversed_entry_id
            timesheet_domain = Domain('timesheet_invoice_id', '=', False) | Domain('timesheet_invoice_id.state', '=', 'cancel')
            if refund_account_moves:
                credited_timesheet_domain = Domain('timesheet_invoice_id.state', '=', 'posted') & Domain('timesheet_invoice_id', 'in', refund_account_moves.ids)
                timesheet_domain = timesheet_domain | credited_timesheet_domain
            # Shortcut to allow computing the domain for a bunch of lines without using _get_deferred_date that does not work in batch.
            # Side effect: It won't work for the first period if the invoice cron never run. (the next invoice date has never been incremented)
            domain = Domain.AND([
                domain,
                timesheet_domain,
                Domain('date', '>=', so.last_invoice_date or so.start_date),
                Domain('date', '<', so.next_invoice_date),
            ])
            mapping = lines_by_timesheet.sudo()._get_delivered_quantity_by_analytic(domain)
            for line in lines:
                delivered_qties[line] = mapping[line.id]
        return delivered_qties
