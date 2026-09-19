# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrContractSalaryBenefit(models.Model):
    _inherit = 'hr.contract.salary.benefit'

    source = fields.Selection(
        selection_add=[('rule', 'Salary Rule')],
        ondelete={'rule': 'cascade'})
    salary_rule_id = fields.Many2one(
        'hr.salary.rule',
        string="Salary Rule",
        domain="[('input_usage_employee', '=', True), ('input_used_in_definition', '=', True), ('struct_id.type_id', '=', structure_type_id)]",
        help="Select the salary rule associated with this benefit",
    )

    @api.depends('salary_rule_id')
    def _compute_field(self):
        for record in self:
            if record.source == 'field':
                record.field = record.res_field_id.name
            elif record.source == 'rule':
                record.field = record.salary_rule_id.name
            else:
                record.field = False
