# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models
from odoo.fields import Domain


_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_type = fields.Selection([
        ('procurement', 'Procurement'),
        ('commission', 'Commission'),
    ], 'Purchase Type', default='procurement', index=True)
    invoice_commission_count = fields.Integer(
        'Source Invoices',
        compute='_compute_source_invoice_count',
        compute_sudo=True,
        help='Invoices that have generated commissions included in this order'
    )

    def _compute_source_invoice_count(self):
        for purchase_order in self:
            purchase_order.invoice_commission_count = self.env['account.move'].search_count(
                [('commission_po_line_id.order_id', 'in', purchase_order.ids)]
            )

    def action_view_customer_invoices(self):
        self.ensure_one()

        res = self.env['ir.actions.act_window']._for_xml_id('partner_commission.action_view_customer_invoices')
        res.update({
            'domain': [('commission_po_line_id.order_id', 'in', self.ids)],
        })
        return res

    @api.model
    def _cron_confirm_purchase_orders(self):
        # Frequency is company dependent.
        template = self.env.ref('purchase.email_template_edi_purchase_done')
        companies = self.env['res.company']
        today = fields.Date.today()
        for company in companies.search([]):
            frequency = company.commission_automatic_po_frequency

            # noop
            if frequency == 'manually':
                continue

            monday = frequency == 'weekly' and today.isoweekday() == 1
            first_of_the_month = frequency == 'monthly' and today.day == 1
            new_quarter = frequency == 'quarterly' and today.day == 1 and today.month in [1, 4, 7, 10]
            run = monday or first_of_the_month or new_quarter

            if not run:
                continue

            companies += company

        precondition = Domain([
            ('company_id', 'in', companies.ids),
            ('date_order', '<', today),
            ('state', '=', 'draft'),
            ('purchase_type', '=', 'commission'),
        ])
        purchases = self.env['purchase.order'].search(precondition).filtered(
            lambda p: p.invoice_commission_count > 0
            and p.currency_id._convert(p.amount_total, p.company_id.currency_id, p.company_id, today) >= p.company_id.commission_po_minimum
        )
        self.env['ir.cron']._commit_progress(remaining=len(purchases))

        for purchase in purchases:
            purchase = purchase.try_lock_for_update(allow_referencing=True).filtered_domain(precondition)
            if not purchase:
                continue
            try:
                purchase.button_confirm()

                if purchase.state == 'purchase':
                    template.send_mail(purchase.id)

                self.env['ir.cron']._commit_progress(1)
            except Exception:
                self.env.rollback()
                _logger.exception('_cron_confirm_purchase_orders: PO (id=%s) could not be confirmed', purchase.id)
