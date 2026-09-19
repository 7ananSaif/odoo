# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'
    _description = 'Salary Structure Type'

    def _get_selection_schedule_pay(self):
        if self.env.company.country_code == 'MX':
            return [
                ('daily', 'Daily'),
                ('weekly', 'Weekly'),
                ('10_days', '10 Days'),
                ('14_days', '14 Days'),
                ('bi-weekly', 'Bi-weekly'),
                ('monthly', 'Monthly'),
                ('bi-monthly', 'Bi-monthly'),
            ]
        return super()._get_selection_schedule_pay()
