# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class BudgetLine(models.Model):
    _inherit = "budget.line"

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        if self.env.context.get('project_update'):
            project = self.env['project.project'].browse(self.env.context.get('active_id'))
            if project.account_id:
                defaults[project.account_id.plan_id._column_name()] = project.account_id.id
        return defaults
