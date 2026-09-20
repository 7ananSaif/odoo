import pytz

from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.tools.intervals import Intervals


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _search_get_detail(self, website, order, options):
        search_details = super()._search_get_detail(website, order, options)
        if (
            (from_date := options.get('from_date'))
            and (to_date := options.get('to_date'))
            and (
                planning_roles := self.env['planning.role'].sudo().search_fetch(
                    [('sync_shift_rental', '=', True)],
                    ['resource_ids'],
                ))
        ):
            unavailable_resources = self.env['planning.slot'].sudo()._read_group(
                [
                    ('start_datetime', '<=', to_date),
                    ('end_datetime', '>=', from_date),
                    ('resource_id', 'in', planning_roles.resource_ids.ids),
                ],
                [],
                ['resource_id:recordset'],
            )[0][0]
            unavailable_intervals_per_resource_id = defaultdict(list)
            if human_resources := planning_roles.resource_ids.filtered(lambda r: r.resource_type != 'material' and r not in unavailable_resources):
                min_date = fields.Datetime.to_datetime(from_date)
                max_date = fields.Datetime.to_datetime(to_date)
                min_date_in_utc = min_date.astimezone(pytz.UTC)
                max_date_in_utc = max_date.astimezone(pytz.UTC)
                date = min_date_in_utc + relativedelta(hour=0, minute=0, second=0, microsecond=0)
                unavailable_intervals_per_calendar_id = defaultdict(Intervals)
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
                    leave_intervals_batch_per_resource_id = calendar.sudo()._leave_intervals_batch(min_date_in_utc, max_date_in_utc, workers)
                    for resource_id, leave_intervals in leave_intervals_batch_per_resource_id.items():
                        if not resource_id:
                            continue
                        unavailable_intervals_per_resource_id[resource_id] = leave_intervals | unavailable_intervals_per_calendar_id[calendar.id]
            search_details['base_domain'].append([
                '|',
                ('planning_enabled', '=', False),
                ('planning_role_id', 'in', planning_roles.filtered(lambda r: r.resource_ids.filtered(lambda r: not unavailable_intervals_per_resource_id[r.id]) - unavailable_resources).ids)
            ])
        return search_details
