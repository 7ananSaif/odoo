# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.sale_subscription.models.sale_order import SUBSCRIPTION_CLOSED_STATE


class StockForecasted_Product_Product(models.AbstractModel):
    _inherit = 'stock.forecasted_product_product'

    def _get_report_header(self, product_template_ids, product_variant_ids, wh_location_ids):
        res = super()._get_report_header(product_template_ids, product_variant_ids, wh_location_ids)
        domain = self._product_active_subscription_domain(product_template_ids, product_variant_ids)
        so_lines = self.env['sale.order.line'].search(domain).grouped('product_id')
        out_qty = {k.id: sum(v.mapped('product_uom_qty')) for k, v in so_lines.items()}
        self._add_product_quantities(res, product_template_ids, product_variant_ids, 'subscription_qty', qty_out=out_qty)
        for product in self._get_products(product_template_ids, product_variant_ids):
            if product not in so_lines:
                continue
            res['product'][product.id]['subscription_sale_orders'] = so_lines[product].mapped("order_id").sorted(key=lambda so: so.name).read(fields=['id', 'name'])
        return res

    def _product_active_subscription_domain(self, product_template_ids, product_variant_ids):
        domain = [
            ('state', '=', 'sale'),
            ('product_template_id.recurring_invoice', '=', True),
            ('order_id.subscription_state', 'not in', SUBSCRIPTION_CLOSED_STATE)
        ]
        if product_template_ids:
            domain += [('product_template_id', 'in', product_template_ids)]
        elif product_variant_ids:
            domain += [('product_id', 'in', product_variant_ids)]
        warehouse_id = self.env.context.get('warehouse_id', False)
        if warehouse_id:
            domain += [('warehouse_id', '=', warehouse_id)]
        return domain

    def _product_sale_domain(self, product_template_ids, product_ids):
        domain = super()._product_sale_domain(product_template_ids, product_ids)
        return domain + [('product_template_id.recurring_invoice', '=', False)]
