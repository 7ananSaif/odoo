from odoo import _, api, fields, models
from odoo.fields import Domain


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_invoice_policy = fields.Selection(related='product_id.invoice_policy')

    deferred_revenue = fields.Boolean(
        string='Deferred Revenue', search="_search_deferred_revenue",
        store=False)
    invoice_to_be_issued = fields.Boolean(
        string='Invoice to be Issued', search="_search_invoice_to_be_issued",
        store=False)

    def _search_deferred_revenue(self, operator, value):
        if operator != '=' or not value:
            raise NotImplementedError(_('Only a check to True is supported'))
        so_lines = self.env['sale.order.line'].search(self._get_accrual_domain())
        ids = [line.id for line in so_lines if line.qty_invoiced_at_date > line.qty_delivered_at_date]
        return Domain([('id', 'in', ids)])

    def _search_invoice_to_be_issued(self, operator, value):
        if operator != '=' or not value:
            raise NotImplementedError(_('Only a check to True is supported'))
        so_lines = self.env['sale.order.line'].search(self._get_accrual_domain())
        ids = [line.id for line in so_lines if line.qty_invoiced_at_date < line.qty_delivered_at_date]
        return Domain([('id', 'in', ids)])

    @api.model
    def _read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[tuple]:
        return self._read_group_for_accrual(domain, groupby, aggregates, having, offset, limit, order)

    @api.model
    def _get_accrual_domain(self):
        return [
            ('product_id', '!=', False),
            ('state', '=', 'sale'),
        ]

    @api.model
    def _get_aggregates_to_skip_and_fields_to_patch(self):
        aggregates_to_skip, fields_to_patch = super()._get_aggregates_to_skip_and_fields_to_patch()
        aggregates_to_skip.insert(0, 'qty_delivered_at_date:sum')
        fields_to_patch.insert(0, 'qty_delivered_at_date')
        return (aggregates_to_skip, fields_to_patch)
