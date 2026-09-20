# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.fields import Domain


class Company(models.Model):
    _inherit = 'res.company'

    @api.model
    def _get_timesheet_reminder_domain(self):
        return Domain.AND([
            super()._get_timesheet_reminder_domain(),
            [('holiday_id', '=', False), ('global_leave_id', '=', False)]
        ])
