# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrPayrollStructureType(models.Model):
    _inherit = "hr.payroll.structure.type"

    l10n_au_default_input_type_ids = fields.Many2many(
        "hr.payslip.input.type",
        string="Default Allowances",
        help="Default allowances for this structure type")

    def _get_selection_schedule_pay(self):
        if self.env.company.country_code == 'AU':
            return [
                ('quarterly', 'Quarterly'),
                ('monthly', 'Monthly'),
                ('bi-weekly', 'Fortnightly'),
                ('weekly', 'Weekly'),
                ('daily', 'Daily'),
            ]
        return super()._get_selection_schedule_pay()
