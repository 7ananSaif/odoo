# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    ongoing_appraisal_count = fields.Integer()
    parent_user_id = fields.Many2one('res.users', compute='_compute_parent_user_id')
    last_appraisal_id = fields.Many2one('hr.appraisal', compute='_compute_last_appraisal_id')
    next_appraisal_date = fields.Date(compute='_compute_manager_only_fields', search='_search_next_appraisal_date')
    can_request_appraisal = fields.Boolean(compute='_compute_can_request_appraisal')
    last_appraisal_state = fields.Selection(
        [('1_new', 'To Confirm'),
         ('2_pending', 'Confirmed'),
         ('3_done', 'Done')], compute='_compute_last_appraisal_state')
    last_appraisal_date = fields.Date(related='employee_id.last_appraisal_id.date_close')

    def _get_manager_only_fields(self):
        return super()._get_manager_only_fields() + ['next_appraisal_date']

    def _search_next_appraisal_date(self, operator, value):
        employees = self.env['hr.employee'].sudo().search([('id', 'child_of', self.env.user.employee_id.ids), ('next_appraisal_date', operator, value)])
        return [('id', 'in', employees.ids)]

    def _compute_parent_user_id(self):
        self._compute_from_employee('parent_user_id')

    def _compute_last_appraisal_id(self):
        self._compute_from_employee('last_appraisal_id')

    def _compute_can_request_appraisal(self):
        self._compute_from_employee('can_request_appraisal')

    def _compute_last_appraisal_state(self):
        self._compute_from_employee('last_appraisal_state')

    def action_open_last_appraisal(self):
        self.ensure_one()
        if self.is_user:
            return {
                'view_mode': 'form',
                'res_model': 'hr.appraisal',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': self.last_appraisal_id.id,
            }

    def action_send_appraisal_request(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.appraisal',
            'name': 'Appraisal Request',
            'context': self.env.context,
        }
