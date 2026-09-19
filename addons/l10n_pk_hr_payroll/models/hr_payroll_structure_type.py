# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'
    _description = 'Salary Structure Type'

    def _get_selection_schedule_pay(self):
        if self.env.company.country_code == 'PK':
            return [('monthly', 'Monthly')]
        return super()._get_selection_schedule_pay()
