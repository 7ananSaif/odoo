from odoo import api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        sale_orders = super().create(vals_list)
        if rental_orders := sale_orders.filtered('is_rental_order'):
            slots_per_rental_order = self.env['planning.slot']._read_group(
                [('sale_order_id', 'in', rental_orders.ids)],
                ['sale_order_id'],
                ['id:recordset'],
            )
            open_shifts = self.env['planning.slot']
            for rental_order, slots in slots_per_rental_order:
                slots_to_update = slots.filtered(
                    lambda s: s.start_datetime != rental_order.rental_start_date or s.end_datetime != rental_order.rental_return_date
                )
                slots_to_update.with_context(rental_order_updated=True).write({
                    'start_datetime': rental_order.rental_start_date,
                    'end_datetime': rental_order.rental_return_date,
                })
                open_shifts += slots.filtered(lambda s: not s.resource_id)
            if open_shifts:
                open_shifts._set_slot_resource()
        return sale_orders

    def write(self, vals):
        rental_start_date = vals.get('rental_start_date')
        rental_return_date = vals.get('rental_return_date')
        rental_orders = self.env['sale.order']
        dates_per_rental_order = {}
        if not self.env.context.get('slots_rescheduled') and (rental_start_date or rental_return_date):
            rental_orders = self.filtered('is_rental_order')
            dates_per_rental_order = {ro: (ro.rental_start_date, ro.rental_return_date) for ro in rental_orders}
        res = super().write(vals)
        if rental_orders:

            def is_slot_to_update(slot):
                start_datetime, end_datetime = dates_per_rental_order[slot.sale_order_id]
                return slot.start_datetime == start_datetime and slot.end_datetime == end_datetime

            if slots := rental_orders.order_line.planning_slot_ids.filtered(is_slot_to_update):
                slots_vals = {}
                if rental_start_date:
                    slots_vals['start_datetime'] = rental_start_date
                if rental_return_date:
                    slots_vals['end_datetime'] = rental_return_date
                slots.with_context(rental_order_updated=True).write(slots_vals)
        return res
