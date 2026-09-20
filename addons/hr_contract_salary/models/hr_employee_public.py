# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    contract_reviews_count = fields.Integer(compute='_compute_contract_reviews_count')
    salary_offers_count = fields.Integer(compute='_compute_salary_offers_count')

    def _compute_contract_reviews_count(self):
        self._compute_from_employee('contract_reviews_count')

    def _compute_salary_offers_count(self):
        self._compute_from_employee('salary_offers_count')
