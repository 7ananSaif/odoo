# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import LazyTranslate

_lt = LazyTranslate(__name__)

SINGULAR_LABELS = {
    'hour': _lt("Hour"),
    'day': _lt("Day"),
    'week': _lt("Week"),
    'month': _lt("Month"),
    'year': _lt("Year"),
}
UNIT_SELECTION = [
    ('hour', "Hours"),
    ('day', "Days"),
    ('week', "Weeks"),
    ('month', "Months"),
    ('year', "Years"),
]


class SaleTemporalRecurrence(models.Model):
    _name = 'sale.temporal.recurrence'
    _description = "Sale temporal Recurrence"
    _order = 'unit,duration'

    active = fields.Boolean(default=True)
    name = fields.Char(translate=True, required=True, default="Monthly")
    duration = fields.Integer(
        required=True,
        default=1,
        help="Minimum duration before this rule is applied. If set to 0, it represents a fixed"
            "rental price.",
    )
    displayed_unit = fields.Selection(
        selection=UNIT_SELECTION + [('night', "Nights")],
        compute="_compute_displayed_unit",
        inverse="_inverse_displayed_unit",
    )
    unit = fields.Selection(
        selection=UNIT_SELECTION,
        required=True,
        default='month',
    )
    # overnight means:
    # - change from 24 -> 1 (duration) and Hour -> Night (unit label)
    # - canSelectHours False (hours but not selectable from the website)
    # - pickup and return times visible in the period form
    overnight = fields.Boolean(string="Overnight")
    pickup_time = fields.Float(string="Check-in")
    return_time = fields.Float(string="Check-out")
    duration_display = fields.Char(compute='_compute_duration_display')

    _check_pickup_time = models.Constraint(
        'CHECK(pickup_time >= 0 AND pickup_time <= 24)',
        "The pickup time has to be between 0 and 24.",
    )
    _check_return_time = models.Constraint(
        'CHECK(return_time >= 0 AND return_time <= 24)',
        "The return time has to be between 0 and 24.",
    )
    _temporal_recurrence_duration = models.Constraint(
        'CHECK(duration >= 0)',
        "The pricing duration has to be greater or equal to 0.",
    )

    # === COMPUTE METHODS === #

    @api.depends('overnight', 'unit')
    def _compute_displayed_unit(self):
        for recurrence in self:
            recurrence.displayed_unit = recurrence.unit if not recurrence.overnight else 'night'

    def _inverse_displayed_unit(self):
        for recurrence in self:
            if recurrence.displayed_unit != 'night':
                recurrence.update({
                    'unit': recurrence.displayed_unit,
                    'overnight': False,
                    'pickup_time': False,
                    'return_time': False,
                })
            else:
                recurrence.update({
                    'unit': 'hour',
                    'duration': 24,
                    'overnight': True,
                })

    def _compute_duration_display(self):
        for recurrence in self:
            display_duration, display_label = recurrence._get_converted_duration_and_label(
                recurrence.duration
            )
            recurrence.duration_display = self.env._(
                "%(duration)s %(unit)s", duration=display_duration, unit=display_label
            )

    # === BUSINESS METHODS === #

    def _get_unit_label(self, duration):
        """ Get the translated product pricing unit label. """
        self.ensure_one()
        if duration == 1:
            return self.env._(SINGULAR_LABELS[self.unit])  # pylint: disable=gettext-variable
        return dict(self._fields['unit']._description_selection(self.env))[self.unit]

    def _get_converted_duration_and_label(self, duration):
        self.ensure_one()
        if self.overnight:
            night_duration = round(duration / 24)
            label = self.env._("Night") if night_duration == 1 else self.env._("Nights")
            return [night_duration, label]
        else:
            return [duration, self._get_unit_label(duration)]
