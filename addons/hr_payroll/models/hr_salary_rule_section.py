from odoo import fields, models


class HrSalaryRuleSection(models.Model):
    _name = 'hr.salary.rule.section'
    _description = 'Salary Input Section'

    name = fields.Char()
    sequence = fields.Integer()
    struct_ids = fields.Many2many('hr.payroll.structure')
