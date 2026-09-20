# Part of Odoo. See LICENSE file for full copyright and licensing details.

from pytz import utc
from random import shuffle

from odoo import models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_round


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _compute_planning_hours_to_plan(self):
        planning_rental_sols = self.filtered(
            lambda sol:
                sol.is_rental
                and sol.state not in ['draft', 'sent']
                and sol.product_id.planning_enabled
        )

        for line in planning_rental_sols:
            if line.planning_slot_ids.resource_id.calendar_id:
                days_per_week = line.company_id.resource_calendar_id.get_work_duration_data(line.start_date, line.return_date)['days']
            else:
                days_per_week = line.order_id.duration_days + (1 if line.order_id.remaining_hours else 0)
            line.planning_hours_to_plan = line.company_id.resource_calendar_id.hours_per_day * days_per_week
        super(SaleOrderLine, self - planning_rental_sols)._compute_planning_hours_to_plan()

    def _planning_slot_vals_list_per_sol(self):
        vals_list_per_sol = super()._planning_slot_vals_list_per_sol()
        assigned_resource_ids = []
        problematic_services = []
        unit_uom = self.env.ref('uom.product_uom_unit')
        for sol, vals_list in vals_list_per_sol.items():
            if not sol.is_rental:
                continue
            available_resources = sol.product_id.planning_role_id.resource_ids
            if not available_resources:
                problematic_services.append(sol.product_id.name)
                continue

            unavailable_resource_slots = self.env['planning.slot'].search([
                ('resource_id', 'in', available_resources.ids),
                ('start_datetime', '<=', sol.return_date),
                ('end_datetime', '>=', sol.start_date),
            ])
            resource_leaves = self.env['resource.calendar.leaves'].search([
                ('resource_id', 'in', available_resources.ids),
                ('date_from', '<=', sol.return_date),
                ('date_to', '>=', sol.start_date),
            ])
            available_resources -= (unavailable_resource_slots.resource_id + resource_leaves.resource_id)
            if not available_resources:
                problematic_services.append(sol.product_id.name)
                continue

            date_from = utc.localize(sol.start_date)
            date_to = utc.localize(sol.return_date)
            work_intervals_per_resource, _dummy = available_resources._get_valid_work_intervals(date_from, date_to, available_resources.calendar_id)
            free_resource_ids = []
            flexible_resource_ids = []
            for available_resource in available_resources:
                if not available_resource.calendar_id:
                    flexible_resource_ids.append(available_resource.id)
                elif not work_intervals_per_resource[available_resource.id]:
                    continue
                if not (assigned_resource_ids and available_resource.id in assigned_resource_ids):
                    free_resource_ids.append(available_resource.id)

            shuffle(free_resource_ids)

            # FIXME: check why it is needed
            if free_resource_ids and free_resource_ids[0] not in flexible_resource_ids:
                days_per_week = sol.company_id.resource_calendar_id.get_work_duration_data(sol.start_date, sol.return_date)['days']
                sol.planning_hours_to_plan = sol.company_id.resource_calendar_id.hours_per_day * days_per_week

            resource_id = False
            if free_resource_ids and len(vals_list) <= len(free_resource_ids):
                for index, vals in enumerate(vals_list):
                    resource_id = free_resource_ids[index]
                    vals['resource_id'] = resource_id
                    assigned_resource_ids.append(resource_id)
                if sol.product_uom_id == unit_uom and float_compare(sol.product_uom_qty, 1, precision_rounding=sol.product_uom_id.rounding) > 0:
                    nb_shifts_to_generate = int(float_round(sol.product_uom_qty, 0, rounding_method="UP"))
                    if len(free_resource_ids) >= nb_shifts_to_generate:
                        vals_list.extend([
                            {**sol._planning_slot_values(), 'resource_id': free_resource_ids[i]}
                            for i in range(1, nb_shifts_to_generate)
                        ])
                    elif sol.product_id.planning_role_id.sync_shift_rental:
                        raise ValidationError(
                            self.env._(
                                "This Sales Order can't be confirmed. No enough resources are available for the shifts in: %(product_name)s.",
                                product_name=sol.product_id.name,
                            )
                        )
            else:
                problematic_services.append(sol.product_id.name)
        if problematic_services and sol.product_id.planning_role_id.sync_shift_rental:
            raise ValidationError(
                self.env._(
                    "This Sales Order can't be confirmed. No resources are available for the shifts in: %(problematic_services)s.",
                    problematic_services=problematic_services,
                )
            )
        return vals_list_per_sol

    def _planning_slot_values(self):
        vals = super()._planning_slot_values()
        if self.is_rental:
            vals.update(
                start_datetime=self.start_date,
                end_datetime=self.return_date,
                state='published',
            )
        return vals

    def write(self, vals):
        if 'product_uom_qty' in vals and vals['product_uom_qty'] == 0 and (rental_sols := self.filtered('is_rental')):
            if slots := self.env['planning.slot'].search([('sale_line_id', 'in', rental_sols.ids)]):
                slots.unlink()
        return super().write(vals)

    def unlink(self):
        rental_order_lines = self.filtered('is_rental')
        if slots := self.env['planning.slot'].search([('sale_line_id', 'in', rental_order_lines.ids)]):
            slots.unlink()
        return super().unlink()
