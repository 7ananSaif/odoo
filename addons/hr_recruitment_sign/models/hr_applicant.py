# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    sign_request_count = fields.Integer(related="partner_id.signature_count")

    def open_applicant_sign_requests(self):
        self.ensure_one()
        if self.partner_id:
            request_ids = self.env['sign.request.item'].search([
                ('partner_id', '=', self.partner_id.id)]).sign_request_id
            if self.env.user.has_group('sign.group_sign_user'):
                view_id = self.env.ref("sign.sign_request_view_kanban").id
            else:
                view_id = self.env.ref("hr_sign.sign_request_employee_view_kanban").id

            return {
                'type': 'ir.actions.act_window',
                'name': _('Signature Requests'),
                'view_mode': 'kanban,list',
                'res_model': 'sign.request',
                'view_ids': [(view_id, 'kanban'), (False, 'list')],
                'domain': [('id', 'in', request_ids.ids)],
                'context': {
                    'applicant_id': self.id,
                    'active_model': 'hr.applicant',
                },
            }

    def _open_applicant_sign_requests(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Signature Request'),
            'res_model': 'hr.recruitment.sign.document.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_employee_create_vals(self):
        vals = super()._get_employee_create_vals()
        request_ids = self.env['sign.request.item'].search([
            ('partner_id', '=', self.partner_id.id)]).sign_request_id
        vals['sign_request_ids'] = request_ids.ids
        return vals
