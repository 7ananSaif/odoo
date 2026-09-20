# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from collections import defaultdict

from odoo import api, models, _
from odoo.exceptions import ValidationError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.model
    def _error_dependencies(self):
        return super()._error_dependencies() + ['employee_id.leave_ids.payslip_state', 'employee_id.leave_ids.state']

    def _get_errors_by_slip(self):
        errors_by_slip = super()._get_errors_by_slip()
        slips_by_employee = self.grouped('employee_id')
        leaves_by_slip = defaultdict(lambda: self.env['hr.leave'])
        for leave in self.employee_id.leave_ids.filtered(
            lambda leave: leave.payslip_state == 'blocked' and leave.state not in ['cancel', 'refuse']
        ):
            for slip in slips_by_employee[leave.employee_id].filtered(lambda ps: ps.state == 'draft'):
                if (slip.date_from <= leave.date_to.date()
                    and leave.date_from.date() <= slip.date_to):
                    leaves_by_slip[slip] |= leave
        for slip, leaves in leaves_by_slip.items():
            errors_by_slip[slip].append({
                'message': _('Employee has time off to defer'),
                'action_text': _("Time Offs"),
                'action': leaves._get_records_action(),
                'level': 'danger',
            })
        return errors_by_slip

    def compute_sheet(self):
        if self.env.context.get('salary_simulation'):
            return super().compute_sheet()
        regular_payslips = self.filtered(lambda p: p.is_regular)
        if regular_payslips:
            employees = regular_payslips.mapped('employee_id')
            leaves = self.env['hr.leave'].search([
                ('employee_id', 'in', employees.ids),
                ('state', '!=', 'refuse'),
            ])
            dates = regular_payslips.mapped('date_to')
            max_date = datetime.combine(max(dates), datetime.max.time())
            leaves_to_green = leaves.filtered(lambda l: l.payslip_state != 'blocked' and l.date_to <= max_date)
            leaves_to_green.write({'payslip_state': 'done'})
        return super().compute_sheet()
