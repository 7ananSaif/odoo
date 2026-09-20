# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_jo_annual_leave_type_id = fields.Many2one("hr.leave.type",
        string="JO Annual Leave Time-off Type",
        default=lambda self: self.env.ref("hr_holidays.leave_type_paid_time_off", raise_if_not_found=False))
