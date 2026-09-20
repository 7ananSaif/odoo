# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def set_values(self):
        super().set_values()
        todo_alias = self.env.ref('project_enterprise_hr.mail_alias_todo', raise_if_not_found=False)
        if not todo_alias and self.alias_domain_id:
            # create alias again if deletes the record created from data
            alias = self.env['mail.alias'].sudo().create({
                'alias_contact': 'employees',
                'alias_model_id': self.env['ir.model']._get_id('project.task'),
                'alias_name': "to-do",
                'alias_defaults': {'project_id': False},
            })
            self.env['ir.model.data'].sudo().create({
                'name': 'mail_alias_todo',
                'module': 'project_enterprise_hr',
                'model': 'mail.alias',
                'noupdate': True,
                'res_id': alias.id,
            })
