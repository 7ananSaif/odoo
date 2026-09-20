# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _build_default_order_line_values(self):
        """Override of `sale_renting` to infer the product from the reserved lots, if not already
        sepcified."""
        defaults = super()._build_default_order_line_values()
        if (
            'product_id' not in defaults
            and (reserved_lot_ids := self.env.context.get('default_reserved_lot_ids'))
        ):
            product_id = self.env['stock.lot'].browse(reserved_lot_ids[:1]).product_id.id
            defaults['product_id'] = product_id

        return defaults

    def action_open_pickup(self):
        if any(s.is_rental for s in self.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')).move_ids.sale_line_id):
            ready_picking = self.picking_ids.filtered(lambda p: p.state == 'assigned' and p.picking_type_code == 'outgoing')
            if ready_picking:
                return self._get_action_view_picking(ready_picking)
            return self._get_action_view_picking(self.picking_ids)
        return super().action_open_pickup()

    def action_open_return(self):
        if any(s.is_rental for s in self.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')).move_ids.sale_line_id):
            ready_picking = self.picking_ids.filtered(lambda p: p.state == 'assigned' and p.picking_type_code == 'incoming')
            if ready_picking:
                return self._get_action_view_picking(ready_picking)
            return self._get_action_view_picking(self.picking_ids)
        return super().action_open_return()
