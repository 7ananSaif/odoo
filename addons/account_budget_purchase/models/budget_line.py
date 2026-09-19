# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class BudgetLine(models.Model):
    _inherit = 'budget.line'

    committed_amount = fields.Monetary(
        compute='_compute_all',
        string='Committed',
        help="Already Billed amount + Confirmed purchase orders.")
    committed_percentage = fields.Float(
        compute='_compute_all',
        string='Committed (%)')

    def _compute_all(self):
        # Override in order to do only one read_group
        grouped = {
            line: (committed, achieved)
            for line, committed, achieved in self.env['budget.report']._read_group(
                domain=[('budget_line_id', 'in', self.ids)],
                groupby=['budget_line_id'],
                aggregates=['committed:sum', 'achieved:sum'],
            )
        }
        for line in self:
            committed, achieved = grouped.get(line, (0, 0))
            line.committed_amount = committed
            line.achieved_amount = achieved
            line.committed_percentage = line.budget_amount and (line.committed_amount / line.budget_amount)
            line.achieved_percentage = line.budget_amount and (line.achieved_amount / line.budget_amount)
