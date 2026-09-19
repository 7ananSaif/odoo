# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.fields import Domain


class StockLot(models.Model):
    _inherit = 'stock.lot'

    def action_auto_assign_lots(self):
        """Automatically assigns available lots to a sale order line based on the provided
        context."""
        if not (sol_id := self.env.context.get('order_line_id')):
            return

        sol = self.env['sale.order.line'].browse(sol_id)
        sol.reserved_lot_ids = (
            sol.reserved_lot_ids | self._get_available_lots(sol.product_id)
        )[:int(sol.product_uom_qty)]

    @api.model
    def _get_available_lots(self, products, location=None):
        """Get all available lots for a set of products.

        :param product.product products: The products to look for.
        :param stock.location location: Optionally, filter for a specific location.
        :rtype: stock.lot
        """
        quant_domain = Domain([
            ('product_id', 'in', products.ids),
            ('lot_id', '!=', False),
            ('location_id.usage', '=', 'internal')
        ])
        if location:
            quant_domain &= Domain.OR([
                Domain('location_id', '=', location.id),
                Domain('location_id', 'child_of', location.id),
            ])

        return self.env['stock.quant'].search(quant_domain).lot_id

    @api.model
    def _get_lots_in_rent(self, product):
        """Company_wise"""
        return self._get_available_lots(product, self.env.company.rental_loc_id)
