from odoo import api, models
from odoo.fields import Domain


class AnalyticMixin(models.AbstractModel):
    _inherit = 'analytic.mixin'

    @api.model
    def _read_group_for_accrual(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[tuple]:
        """ This method is called instead of usual `_read_group` to compute the
        sum of non-storedcomputed fields. It's used in the accrual views,
        by `purchase.order.line` and `sale.order.line` models.
        """
        aggregates_to_skip, fields_to_patch = self._get_aggregates_to_skip_and_fields_to_patch()
        fields_index = {}
        for field in fields_to_patch:
            field_aggregate = f'{field}:sum'
            if field_aggregate in aggregates:
                fields_index[field] = aggregates.index(field_aggregate)
        if not fields_index.keys():
            return super()._read_group(domain, groupby, aggregates, having, offset, limit, order)

        aggregates_2_0 = tuple(a for a in aggregates if a not in aggregates_to_skip)
        res = super()._read_group(domain, groupby, aggregates_2_0, having, offset, limit, order)

        # Make the aggregate sum "manually".
        patched_res = []
        for group in res:
            field_name = groupby[0]
            if ':' in field_name:
                # Support of group by date fields.
                field_name = field_name.split(':')[0]
            # Distinct related fields.
            group_criteria = group[0].id if isinstance(group[0], models.Model) else group[0]
            records = self.env[self._name].search(Domain.AND([
                domain,
                self._get_accrual_domain(),
                [(field_name, '=', group_criteria)]
            ]))
            new_tuple = list(group)
            for field, index in fields_index.items():
                sum_qty_received = sum(rec[field] for rec in records)
                new_tuple.insert(index + 1, sum_qty_received)
            patched_res.append(tuple(new_tuple))
        return patched_res

    @api.model
    def _get_accrual_domain(self):
        return [('product_id', '!=', False)]

    @api.model
    def _get_aggregates_to_skip_and_fields_to_patch(self):
        return (
            ['qty_invoiced_at_date:sum', 'amount_to_invoice_at_date:sum'],
            ['qty_invoiced_at_date', 'amount_to_invoice_at_date']
        )
