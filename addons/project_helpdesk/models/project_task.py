# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def action_convert_to_ticket(self):
        if any(task.recurring_task for task in self):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': self.env._('Recurring tasks cannot be converted into tickets.'),
                }
            }
        if any(task.is_template for task in self):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': self.env._('Tasks templates cannot be converted into tickets.'),
                }
            }
        return {
            'name': self.env._('Convert to Ticket'),
            'view_mode': 'form',
            'res_model': 'project.task.convert.wizard',
            'views': [(False, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                **self.env.context,
                'to_convert': self.ids,
                'dialog_size': 'medium',
            },
        }
