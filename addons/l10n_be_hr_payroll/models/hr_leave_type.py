from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    l10n_be_no_consecutive_leaves_allowed = fields.Boolean(string="No Consecutive Leaves Allowed", default=False)
