# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    document_count = fields.Integer(related='user_partner_id.document_count')

    def action_see_documents(self):
        self.ensure_one()
        if self.is_user:
            return self.user_partner_id.action_see_documents()
