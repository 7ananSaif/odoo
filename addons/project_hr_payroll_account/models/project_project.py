# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from collections import Counter


class ProjectProject(models.Model):
    _inherit = 'project.project'

    contracts_count = fields.Integer('# Contracts', compute='_compute_contracts_count', groups='hr_payroll.group_hr_payroll_user', export_string_translation=False)

    @api.depends('account_id')
    def _compute_contracts_count(self):
        contracts_data = self.env['hr.version'].search([('analytic_distribution', '!=', False)])
        mapped_accounts = contracts_data.mapped('distribution_analytic_account_ids').ids
        project_count = Counter(mapped_accounts)
        for project in self:
            project.contracts_count = project_count.get(project.account_id.id, 0)

    # -------------------------------------------
    # Actions
    # -------------------------------------------

    def action_open_project_contracts(self):
        all_contracts = self.env['hr.version'].search([('analytic_distribution', '!=', False)])
        contracts = all_contracts.filtered(lambda c: self.account_id.id in c.distribution_analytic_account_ids.ids)
        action = self.env["ir.actions.actions"]._for_xml_id("hr.action_hr_version")
        action.update({
            'views': [[False, 'list'], [False, 'form'], [False, 'kanban']],
            'context': {'default_analytic_distribution': {self.account_id.id: 100}},
            'domain': [('id', 'in', contracts.ids)]
        })
        if len(contracts) == 1:
            action["views"] = [[False, 'form']]
            action["res_id"] = contracts.id
        return action

    # ----------------------------
    #  Project Updates
    # ----------------------------

    def _get_stat_buttons(self):
        buttons = super()._get_stat_buttons()
        if self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            buttons.append({
                'icon': 'book',
                'text': self.env._('Contracts'),
                'number': self.contracts_count,
                'action_type': 'object',
                'action': 'action_open_project_contracts',
                'show': self.contracts_count > 0,
                'sequence': 57,
            })
        return buttons
