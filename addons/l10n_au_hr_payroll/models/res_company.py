# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_au_branch_code = fields.Char(
        string="Branch Code",
        help="The branch code of the company, if any.")
    l10n_au_wpn_number = fields.Char(
        string="Withholding Payer Number",
        help="Number given to individuals / enterprises that have PAYGW obligations but don't have an ABN.")
    l10n_au_registered_for_whm = fields.Boolean("Registered for Working Holiday Maker")
    l10n_au_registered_for_palm = fields.Boolean("Registered for PALM Scheme")

    l10n_au_previous_bms_id = fields.Char("Previous BMS ID")
    l10n_au_bms_id = fields.Char("BMS ID", readonly=False)

    def _prepare_resource_calendar_values(self):
        """
        Override to set the default calendar to
        38 hours/week for Australian companies
        """
        vals = super()._prepare_resource_calendar_values()
        if self.country_id.code == 'AU':
            vals.update({
                'name': _('Standard 38 hours/week - %s', self.name),
                'full_time_required_hours': 38.0,
                'tz': 'Australia/Sydney',
                'attendance_ids': [
                    (0, 0, {'name': _('Monday Morning'), 'dayofweek': '0', 'hour_from': 8.5, 'hour_to': 12, 'day_period': 'morning'}),
                    (0, 0, {'name': _('Monday Lunch'), 'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                    (0, 0, {'name': _('Monday Afternoon'), 'dayofweek': '0', 'hour_from': 13, 'hour_to': 17.1, 'day_period': 'afternoon'}),
                    (0, 0, {'name': _('Tuesday Morning'), 'dayofweek': '1', 'hour_from': 8.5, 'hour_to': 12, 'day_period': 'morning'}),
                    (0, 0, {'name': _('Tuesday Lunch'), 'dayofweek': '1', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                    (0, 0, {'name': _('Tuesday Afternoon'), 'dayofweek': '1', 'hour_from': 13, 'hour_to': 17.1, 'day_period': 'afternoon'}),
                    (0, 0, {'name': _('Wednesday Morning'), 'dayofweek': '2', 'hour_from': 8.5, 'hour_to': 12, 'day_period': 'morning'}),
                    (0, 0, {'name': _('Wednesday Lunch'), 'dayofweek': '2', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                    (0, 0, {'name': _('Wednesday Afternoon'), 'dayofweek': '2', 'hour_from': 13, 'hour_to': 17.1, 'day_period': 'afternoon'}),
                    (0, 0, {'name': _('Thursday Morning'), 'dayofweek': '3', 'hour_from': 8.5, 'hour_to': 12, 'day_period': 'morning'}),
                    (0, 0, {'name': _('Thursday Lunch'), 'dayofweek': '3', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                    (0, 0, {'name': _('Thursday Afternoon'), 'dayofweek': '3', 'hour_from': 13, 'hour_to': 17.1, 'day_period': 'afternoon'}),
                    (0, 0, {'name': _('Friday Morning'), 'dayofweek': '4', 'hour_from': 8.5, 'hour_to': 12, 'day_period': 'morning'}),
                    (0, 0, {'name': _('Friday Lunch'), 'dayofweek': '4', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                    (0, 0, {'name': _('Friday Afternoon'), 'dayofweek': '4', 'hour_from': 13, 'hour_to': 17.1, 'day_period': 'afternoon'})
                ],
            })
        return vals
