# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def copy_data(self, default=None):
        # override picking linked to subscriptions to make sure the date are copied
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        for old_picking, vals in zip(self, vals_list):
            order = old_picking.sale_id
            if order.is_subscription:
                if not 'scheduled_date' in vals:
                    vals['scheduled_date'] = old_picking.scheduled_date
                if 'move_ids' in vals:
                    old_picking._update_move_copy_vals(vals['move_ids'])
        return vals_list

    def _update_move_copy_vals(self, move_vals_list):
        self.ensure_one()
        for move, move_vals in zip(self.move_ids, move_vals_list):
            move_dict = len(move_vals) == 3 and move_vals[2]
            if move_dict:
                move_dict['date'] = move.date
        return move_vals_list

    def _action_done(self):
        res = super()._action_done()
        picking_per_so = defaultdict(lambda: self.env['stock.picking'])
        for move in self.move_ids:
            picking = move.picking_id
            sale_order = picking.sale_id
            # Creates new SO line only when pickings linked to a sale order and
            # for moves with qty. done and not already linked to a SO line.
            if not sale_order or move.location_dest_id.usage != 'customer' or not move.picked:
                continue

            if sale_order.subscription_state == "7_upsell":
                # we need to compute the parent id, because it was not computed when we created the SOL in _subscription_update_line_data
                self.env.add_to_compute(self.env['sale.order.line']._fields['parent_line_id'], move.sale_line_id)
                for line in move.sale_line_id:
                    if line.parent_line_id:
                        line.parent_line_id.qty_delivered += line.qty_delivered
            elif sale_order.subscription_state and sale_order.id not in picking_per_so:
                for sol in sale_order.order_line:
                    line_invoiced_date = sol.last_invoiced_date
                    order_invoice_date = sol.order_id.invoice_ids and sol.order_id.last_invoice_date and sol.order_id.last_invoice_date - relativedelta(days=1)
                    last_invoiced_date = line_invoiced_date or order_invoice_date
                    if last_invoiced_date and picking.date_done.date() <= last_invoiced_date:
                        picking_per_so[sol.order_id.id] += move.picking_id

        for so_id, moves in picking_per_so.items():
            order = self.env['sale.order'].browse(so_id)
            unique_moves = set(moves)
            order._post_subscription_activity(
                record=unique_moves,
                summary=self.env._("Delivered Product(s) (Already Invoiced)"),
                explanation=self.env._("New picking has been confirmed"),
            )
        return res
