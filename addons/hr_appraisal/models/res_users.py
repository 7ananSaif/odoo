# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'

    def get_employee_autocomplete_ids(self):
        self.ensure_one()
        Employee = self.env['hr.employee']
        if self.env.user.has_group('hr_appraisal.group_hr_appraisal_user'):
            return Employee.search([('company_id', 'in', self.env.companies.ids)])
        user_employees = Employee.search([('user_id', '=', self.env.user.id)])
        children = Employee
        if user_employees:
            children = Employee.search([
                ('id', 'child_of', user_employees.ids),
                ('company_id', 'in', self.env.companies.ids),
            ])
        return children | self.env.user.employee_ids
