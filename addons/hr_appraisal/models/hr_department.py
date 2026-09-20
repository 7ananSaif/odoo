# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast

from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    appraisals_to_process_count = fields.Integer(compute='_compute_appraisals_to_process', string='Appraisals to Process')
    appraisal_template_ids = fields.Many2many("hr.appraisal.template", 'hr_appraisal_template_hr_department_rel', 'hr_department_id', string="Appraisal Templates")
    appraisal_properties_definition = fields.PropertiesDefinition('Appraisal Properties')

    def _compute_appraisals_to_process(self):
        appraisals = self.env['hr.appraisal']._read_group(
            [('department_id', 'in', self.ids), ('state', 'in', ['1_new', '2_pending'])], ['department_id'], ['__count'])
        result = {department.id: count for department, count in appraisals}
        for department in self:
            department.appraisals_to_process_count = result.get(department.id, 0)

    def action_open_appraisals(self):
        action = self.env["ir.actions.actions"]._for_xml_id("hr_appraisal.open_view_hr_appraisal_graph_department")
        action['context'] = {
            **ast.literal_eval(action['context']),
            'search_default_department_id': self.id,
        }
        return action
