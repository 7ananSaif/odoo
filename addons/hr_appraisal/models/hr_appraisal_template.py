# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrAppraisalTemplate(models.Model):
    _name = 'hr.appraisal.template'
    _description = "Employee Appraisal Template"
    _rec_name = 'description'
    _order = 'sequence, description, id'

    description = fields.Char(required=True, string="Short Name")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company,
        domain=lambda self: [('id', 'in', self.env.companies.ids)])
    sequence = fields.Integer(default=10)
    department_ids = fields.Many2many('hr.department', string="Departments",
        domain="(company_id and [('company_id', 'in', [company_id, False])] or [('company_id', 'in', allowed_company_ids)])")
    appraisal_employee_feedback_template = fields.Html('Employee Feedback', store=True, readonly=False, translate=True)
    appraisal_manager_feedback_template = fields.Html('Manager Feedback', store=True, readonly=False, translate=True)

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [dict(vals, description=self.env._("%s (copy)", template.description)) for template, vals in zip(self, vals_list)]
