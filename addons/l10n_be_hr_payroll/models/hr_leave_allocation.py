from odoo import models, fields


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    max_leaves_allocated = fields.Float(string='Max Leaves Allocated', default=20, readonly=True)
