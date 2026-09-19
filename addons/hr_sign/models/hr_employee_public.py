# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    sign_request_count = fields.Integer(compute='_compute_sign_request_count')
    sign_request_ids = fields.Many2many('sign.request', compute='_compute_sign_request_ids')

    def _compute_sign_request_count(self):
        self._compute_from_employee('sign_request_count')

    def _compute_sign_request_ids(self):
        self._compute_from_employee('sign_request_ids')

    def open_employee_sign_requests(self):
        self.ensure_one()
        if self.is_user:
            return self.user_id.open_employee_sign_requests()
