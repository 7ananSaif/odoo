# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'

    def open_employee_sign_requests(self):
        self.ensure_one()
        contracts = self.sudo().env['hr.version'].search([('employee_id', 'in', self.env.user.employee_ids.ids)])
        sign_from_contract = contracts.mapped('sign_request_ids')
        sign_from_role = self.env['sign.request.item'].sudo().search([
            ('partner_id', '=', self.partner_id.id),
            ('role_id', '=', self.env.ref('hr_sign.sign_item_role_employee_signatory').id)]).mapped('sign_request_id')
        sign_request_ids = sign_from_contract + sign_from_role
        if len(sign_request_ids.ids) == 1:
            return sign_request_ids.go_to_document()

        if self.env.user.has_group('sign.group_sign_user'):
            view_id = self.env.ref("sign.sign_request_view_kanban").id
        else:
            view_id = self.env.ref("hr_sign.sign_request_employee_view_kanban").id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Signature Requests',
            'view_mode': 'kanban,list',
            'res_model': 'sign.request',
            'view_ids': [(view_id, 'kanban'), (False, 'list')],
            'domain': [('id', 'in', sign_request_ids.ids)]
        }
