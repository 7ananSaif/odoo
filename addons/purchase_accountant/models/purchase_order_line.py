from odoo import _, api, fields, models
from odoo.fields import Domain


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_categ_id = fields.Many2one(related='product_id.categ_id')

    prepaid_expense = fields.Boolean(
        string='Prepaid Expense', search="_search_prepaid_expense",
        store=False)
    bill_to_receive = fields.Boolean(
        string='Bill to Receive', search="_search_bill_to_receive",
        store=False)

    def _search_prepaid_expense(self, operator, value):
        if operator != '=' or not value:
            raise NotImplementedError(_('Only a check to True is supported'))
        po_lines = self.env['purchase.order.line'].search(self._get_accrual_domain())
        ids = [line.id for line in po_lines if (line.qty_invoiced_at_date and line.qty_invoiced_at_date > line.qty_received_at_date)]
        return Domain([('id', 'in', ids)])

    def _search_bill_to_receive(self, operator, value):
        if operator != '=' or not value:
            raise NotImplementedError(_('Only a check to True is supported'))
        po_lines = self.env['purchase.order.line'].search(self._get_accrual_domain())
        ids = [line.id for line in po_lines if (line.qty_received_at_date and line.qty_invoiced_at_date < line.qty_received_at_date)]
        return Domain([('id', 'in', ids)])

    @api.model
    def _read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[tuple]:
        return self._read_group_for_accrual(domain, groupby, aggregates, having, offset, limit, order)

    @api.model
    def _get_accrual_domain(self):
        return [
            ('product_id', '!=', False),
            ('state', '=', 'purchase'),
        ]

    @api.model
    def _get_aggregates_to_skip_and_fields_to_patch(self):
        aggregates_to_skip, fields_to_patch = super()._get_aggregates_to_skip_and_fields_to_patch()
        aggregates_to_skip.insert(0, 'qty_received_at_date:sum')
        fields_to_patch.insert(0, 'qty_received_at_date')
        return (aggregates_to_skip, fields_to_patch)
