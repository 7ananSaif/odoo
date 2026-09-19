# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class HrAttendanceOvertimeRule(models.Model):
    _name = 'hr.attendance.overtime.rule'
    _inherit = 'hr.attendance.overtime.rule'

    @api.model
    def _get_default_work_entry_type_id(self):
        return self.env['hr.work.entry.type'].browse(
            self.env['hr.version']._get_default_work_entry_type_overtime_id()
        )

    work_entry_type_id = fields.Many2one('hr.work.entry.type', required=True, default=_get_default_work_entry_type_id)
    amount_rate = fields.Float(
       "Salary Rate",
       compute='_compute_amount_rate',
       store=True,
       readonly=False
    )

    _if_paid_work_entry_type_defined = models.Constraint(
        'CHECK(NOT paid OR work_entry_type_id IS NOT NULL)',
        "if paid the work entry should be defined"
    )

    @api.depends('work_entry_type_id')
    def _compute_amount_rate(self):
        for rule in self:
            rule.amount_rate = rule.work_entry_type_id.amount_rate

    def _extra_overtime_vals(self):
        if not self:
            return {**super()._extra_overtime_vals(), 'work_entry_type_id': False}

        max_rate_rule = max(self, key=lambda r: (r.amount_rate, r.sequence))
        return {
            **super()._extra_overtime_vals(),
            'work_entry_type_overtime_id': max_rate_rule.work_entry_type_id.id,
        }
