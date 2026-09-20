# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    has_slots = fields.Boolean(compute='_compute_has_slots')

    def _compute_has_slots(self):
        self._compute_from_employee('has_slots')

    def action_view_planning(self):
        self.ensure_one()
        if self.is_user:
            return self.employee_id.action_view_planning()
