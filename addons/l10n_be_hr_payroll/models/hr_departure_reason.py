# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrDepartureReason(models.Model):
    _inherit = "hr.departure.reason"

    l10n_be_reason_code = fields.Integer("Reason Code (BE)")

    def _l10n_be_get_default_departure_reasons_codes_by_name(self):
        return {
            'retired': 340,
            'fired': 342,
            'resigned': 343,
            'freelance': 350,
            'agreement': 351,
        }
