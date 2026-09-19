from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_eg_annual_leave_type_id = fields.Many2one(
        'hr.leave.type', string="Annual Leave Time-off Type",
        default=lambda self: self.env.ref('hr_holidays.leave_type_paid_time_off', raise_if_not_found=False))
