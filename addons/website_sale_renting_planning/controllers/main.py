# Part of Odoo. See LICENSE file for full copyright and licensing details.
import pytz

from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.http import request, route
from odoo.tools.intervals import Intervals

from odoo.addons.website_sale_renting.controllers.main import WebsiteSaleRenting


class WebsiteSalePlanningRenting(WebsiteSaleRenting):

    @route()
    def renting_product_availabilities(self, product_id, min_date, max_date):
        product_sudo = request.env['product.product'].sudo().browse(product_id).exists()
        result = super().renting_product_availabilities(product_id, min_date, max_date)
        if (
            product_sudo.type == 'service'
            and product_sudo.rent_ok
            and product_sudo.planning_enabled
            and (resources := product_sudo.planning_role_id.filtered('sync_shift_rental').resource_ids)
        ):
            min_date = fields.Datetime.to_datetime(min_date)
            max_date = fields.Datetime.to_datetime(max_date)
            slots_sudo = self.env['planning.slot'].sudo().search([
                ('resource_id', 'in', resources.ids),
                ('start_datetime', '<=', max_date),
                ('end_datetime', '>=', min_date),
            ], order='start_datetime')  # In sudo mode to access to planning slots' fields from eCommerce.
            rented_quantities = defaultdict(int)
            slot_periods_per_resource = {}
            for resource, slots in slots_sudo.grouped('resource_id').items():
                slot_periods_per_resource[resource.id] = Intervals([])
                for slot in slots:
                    rented_quantities[slot.start_datetime] += 1
                    rented_quantities[slot.end_datetime] -= 1
                    slot_periods_per_resource[resource.id] |= Intervals([(pytz.UTC.localize(slot.start_datetime), pytz.UTC.localize(slot.end_datetime), slot)])

            if human_resources := resources.filtered(lambda r: r.resource_type != 'material'):
                min_date_in_utc = pytz.UTC.localize(min_date)
                max_date_in_utc = pytz.UTC.localize(max_date)
                unavailable_intervals_per_resource_id = defaultdict(list)
                unavailable_intervals_per_calendar_id = defaultdict(Intervals)
                date = min_date_in_utc + relativedelta(hour=0, minute=0, second=0, microsecond=0)
                while date < max_date_in_utc + relativedelta(days=1):
                    for calendar in human_resources.calendar_id:
                        if not calendar._works_on_date(date):
                            unavailable_intervals_per_calendar_id[calendar.id] |= Intervals([(
                                date,
                                date + relativedelta(hour=23, minute=59, second=59, microsecond=999999),
                                calendar
                            )])
                    date += relativedelta(days=1)
                for calendar, workers in human_resources.grouped('calendar_id').items():
                    leave_intervals_batch_per_resource_id = calendar._leave_intervals_batch(min_date_in_utc, max_date_in_utc, workers)
                    for resource_id, leave_intervals in leave_intervals_batch_per_resource_id.items():
                        if not resource_id:
                            continue
                        unavailable_intervals_per_resource_id[resource_id] = leave_intervals | unavailable_intervals_per_calendar_id[calendar.id]
                for resource_id, intervals in unavailable_intervals_per_resource_id.items():
                    slot_intervals = slot_periods_per_resource.get(resource_id, Intervals())
                    for start_dt, end_dt, _dummy in intervals - slot_intervals:
                        if start_dt < max_date_in_utc and end_dt > min_date_in_utc:
                            naive_start_dt = max(start_dt, min_date_in_utc).astimezone(pytz.UTC).replace(tzinfo=None)
                            naive_end_dt = min(end_dt, max_date_in_utc).astimezone(pytz.UTC).replace(tzinfo=None)
                            rented_quantities[naive_start_dt] += 1
                            rented_quantities[naive_end_dt] -= 1
            key_dates = sorted(set(rented_quantities.keys()) | {min_date, max_date})

            availabilities = []
            current_qty_available = len(resources)
            for i in range(1, len(key_dates)):
                start_dt = key_dates[i - 1]
                if start_dt > max_date:
                    break
                current_qty_available -= rented_quantities[start_dt]
                if start_dt >= min_date:
                    availabilities.append({
                        'start': start_dt,
                        'end': key_dates[i],
                        'quantity_available': current_qty_available,
                    })
            result['renting_availabilities'] = availabilities
        return result
