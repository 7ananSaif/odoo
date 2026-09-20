import math
import re

from datetime import time
from odoo import api, fields, models, _
from odoo.tools import format_time
from odoo.tools.date_utils import float_to_time
from odoo.exceptions import ValidationError


class PlanningSlotTemplate(models.Model):
    _name = 'planning.slot.template'
    _description = "Shift Template"
    _order = "sequence"
    _rec_names_search = ['name', 'role_id']

    active = fields.Boolean('Active', default=True)
    name = fields.Char('Hours', compute="_compute_name", store=True)
    sequence = fields.Integer(export_string_translation=False, index=True)
    role_id = fields.Many2one('planning.role', string="Role")
    start_time = fields.Float('Planned Hours', aggregator=None, default_export_compatible=True, default=8.0)
    end_time = fields.Float('End Hour', aggregator=None, default_export_compatible=True, default=17.0)
    duration_days = fields.Integer('Duration Days', default=1, aggregator=None, default_export_compatible=True)

    _check_start_time_lower_than_24 = models.Constraint(
        'CHECK(start_time < 24)',
        "The start hour cannot be greater than 24.",
    )
    _check_start_time_positive = models.Constraint(
        'CHECK(start_time >= 0)',
        "The start hour cannot be negative.",
    )
    _check_duration_days_positive = models.Constraint(
        'CHECK(duration_days > 0)',
        "The span must be at least 1 working day.",
    )

    @api.constrains('start_time', 'end_time', 'duration_days')
    def _check_start_and_end_times(self):
        for template in self:
            if template.end_time < template.start_time and template.duration_days <= 1:
                raise ValidationError(_('The start hour cannot be before the end hour for a one-day shift template.'))

    @api.depends('start_time', 'end_time')
    def _compute_name(self):
        for shift_template in self:
            shift_template.name = shift_template._get_name()

    @api.depends('name', 'duration_days', 'role_id')
    def _compute_display_name(self):
        for shift_template in self:
            display_name = [shift_template._get_name(time_condensed=True)]
            if shift_template.duration_days > 1:
                display_name.append(_('(%s days span)', shift_template.duration_days))
            if shift_template.role_id:
                display_name.append(shift_template.role_id.name)
            shift_template.display_name = ' '.join(display_name)

    @api.model
    def formatted_read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[dict]:
        res = super().formatted_read_group(domain, groupby, aggregates, having, limit, offset, order)
        for data in res:
            if 'start_time' in data:
                data['start_time'] = float_to_time(data['start_time']).strftime('%H:%M')
            if 'end_time' in data:
                data['end_time'] = float_to_time(data['end_time']).strftime('%H:%M')
        return res

    def _get_name(self, time_condensed=False):
        if not (0 <= self.start_time < 24 and 0 <= self.end_time < 24):
            raise ValidationError(_('The start and end hours must be greater or equal to 0 and lower than 24.'))

        def _format_time(float_time):
            time_str = format_time(
                self.env,
                time(hour=int(float_time), minute=min(59, round(math.modf(float_time)[0] / (1 / 60.0)))),
                time_format='HH:mm'
            )
            match = re.match(r'0?(\d{1,2}):(\d{2})', time_str)
            if match:
                hour = match.group(1)
                minute = match.group(2)
                if time_condensed and minute == '00':
                    return hour
                else:
                    return f"{hour}:{minute}"
            return time_str

        start_time_formatted = _format_time(self.start_time)
        end_time_formatted = _format_time(self.end_time)

        return '%s - %s' % (
            start_time_formatted,
            end_time_formatted,
        )
