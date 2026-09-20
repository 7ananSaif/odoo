import pytz

from ast import literal_eval
from collections import defaultdict
from random import shuffle

from odoo import Command, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
from odoo.tools.intervals import Intervals


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    role_sync_shift_rental = fields.Boolean(related='role_id.sync_shift_rental')

    def write(self, vals):
        res = super().write(vals)
        if (
            not self.env.context.get('rental_order_updated')
            and any(vals.get(k) for k in ['start_datetime', 'end_datetime'])
            and (rental_orders := self.exists().filtered('role_sync_shift_rental').sale_order_id.filtered('is_rental_order'))
        ):
            shifts_per_sale_order = self.env['planning.slot']._read_group(
                [
                    ('sale_order_id', 'in', rental_orders.ids),
                ],
                ['sale_order_id'],
                ['id:recordset'],
            )
            updated_sale_order_ids = []
            for sale_order, shifts in shifts_per_sale_order:
                min_start_datetime = min(shifts.mapped('start_datetime'))
                max_end_datetime = max(shifts.mapped('end_datetime'))
                rental_order_vals = {}
                if sale_order.rental_start_date != min_start_datetime:
                    rental_order_vals['rental_start_date'] = min_start_datetime
                if sale_order.rental_return_date != max_end_datetime:
                    rental_order_vals['rental_return_date'] = max_end_datetime
                if rental_order_vals:
                    sale_order.sudo().with_context(slots_rescheduled=True).write(rental_order_vals)
                    updated_sale_order_ids.append(sale_order.id)
            if updated_sale_order_ids:
                SaleOrderLine = self.env['sale.order.line']
                self.env.add_to_compute(
                    SaleOrderLine._fields['name'],
                    SaleOrderLine.sudo().search([('order_id', 'in', updated_sale_order_ids), ('is_rental', '=', True)])
                )
        return res

    def action_create_order(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('sale_renting.rental_order_action')
        context = literal_eval(action.get('context', '{}'))
        context.update(
            default_is_rental_order=True,
            default_rental_start_date=self.start_datetime,
            default_rental_return_date=self.end_datetime,
        )
        if products := self.role_id.product_ids.filtered('rent_ok'):
            uom_hour = self.env.ref('uom.product_uom_hour')
            context['default_order_line'] = [
                Command.create({
                    'product_id': products[0].product_variant_id.id,
                    'is_rental': True,
                    'product_uom_qty': self.allocated_hours if products[:1].uom_id == uom_hour else 1,
                    'planning_slot_ids': self.ids,
                }),
            ]
        return {
            **action,
            'view_mode': 'form',
            'views': [(view_id, view_type) for view_id, view_type in action['views'] if view_type == 'form'],
            'target': 'current',
            'context': context,
        }

    def action_add_last_order(self):
        self.ensure_one()
        order = self.env['sale.order'].search([
            ('is_rental_order', '=', True),
            ('user_id', '=', self.env.uid),
            ('state', '=', 'sale'),
        ], limit=1)
        if not order:
            raise ValidationError(self.env._('No Rental Order is found.'))
        products = self.role_id.product_ids.filtered('rent_ok')
        for sol in order.order_line:
            if sol.product_template_id in products and float_compare(sol.planning_hours_to_plan, 0, precision_rounding=sol.product_uom_id.rounding) == 0:
                self.sale_line_id = sol
                break
        if not self.sale_line_id:
            uom_hour = self.env.ref('uom.product_uom_hour')
            sale_line = order.order_line.filtered(
                lambda l: l.is_rental and l.product_template_id in products
            )[:1]
            if sale_line:
                self.sale_line_id = sale_line
                sale_line.product_uom_qty = (
                    sum(slot.allocated_hours for slot in sale_line.planning_slot_ids)
                    if sale_line.product_uom_id == uom_hour else len(sale_line.planning_slot_ids)
                )
            else:
                product = products[:1]
                self.sale_line_id = self.env['sale.order.line'].with_context(planning_slot_generation=False).create({
                    'product_id': product.product_variant_id.id,
                    'is_rental': True,
                    'product_uom_qty': self.allocated_hours if product.uom_id == uom_hour else 1,
                    'order_id': order.id,
                    'planning_slot_ids': self.ids,
                })
        self.state = 'published'
        if not self.resource_id:
            self._set_slot_resource()
        if not (order.rental_start_date == self.start_datetime and order.rental_return_date == self.end_datetime):
            min_start_datetime, max_end_datetime = self.env['planning.slot']._read_group(
                [('sale_order_id', '=', order.id)],
                [],
                ['start_datetime:min', 'end_datetime:max'],
            )[0]
            order.with_context(slots_rescheduled=True).write({'rental_start_date': min_start_datetime, 'rental_return_date': max_end_datetime})
            SaleOrderLine = self.env['sale.order.line']
            self.env.add_to_compute(
                SaleOrderLine._fields['name'],
                order.order_line.filtered('is_rental')
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._('Shift added to last order'),
            },
        }

    def _set_slot_resource(self):
        # ensure role id is correctly set
        for slot in self:
            if not slot.role_id and slot.sale_line_id:
                slot.role_id = slot.sale_line_id.sudo().product_id.planning_role_id
        resources_per_role = dict(
            self.env['resource.resource']._read_group(
                [('role_ids', 'in', self.role_id.ids)],
                ['role_ids'],
                ['id:recordset'],
            )
        )
        available_resources = self.role_id.resource_ids
        if not available_resources:
            return

        def get_utc_timezone(utc_datetime):
            return pytz.utc.localize(utc_datetime)

        min_start_datetime = min(self.mapped('start_datetime'))
        max_end_datetime = max(self.mapped('end_datetime'))
        slots_per_resource = self.env['planning.slot']._read_group([
            ('resource_id', 'in', available_resources.ids),
            ('start_datetime', '<=', max_end_datetime),
            ('end_datetime', '>=', min_start_datetime),
        ], ['resource_id'], ['id:recordset'])
        unavailable_intervals_per_resource = defaultdict(Intervals)
        for resource, slots in slots_per_resource:
            unavailable_intervals_per_resource[resource.id] |= Intervals([(get_utc_timezone(s.start_datetime), get_utc_timezone(s.end_datetime), s) for s in slots])
        work_intervals_per_resource, _dummy = available_resources._get_valid_work_intervals(get_utc_timezone(min_start_datetime), get_utc_timezone(max_end_datetime))
        problematic_shifts = self.env['planning.slot']
        for slot in self:
            slot_interval = Intervals([(get_utc_timezone(slot.start_datetime), get_utc_timezone(slot.end_datetime), slot)])
            resources = resources_per_role.get(slot.role_id, self.env['resource.resource'])
            free_resources = []
            for resource in resources:
                work_intervals = work_intervals_per_resource[resource.id]
                unavailable_intervals = unavailable_intervals_per_resource.get(resource.id, Intervals())
                if not (unavailable_intervals & slot_interval) and (work_intervals & slot_interval):
                    free_resources.append(resource)

            shuffle(free_resources)

            resource = self.env['resource.resource']
            if free_resources:
                slot.resource_id = free_resources[0]
            else:
                problematic_shifts += slot
        if problematic_shifts:
            raise ValidationError(
                self.env._(
                    "No resources are available for the shifts in: %s.",
                    ", ".join(problematic_shifts.sale_line_id.product_id.mapped('name'))
                )
            )
