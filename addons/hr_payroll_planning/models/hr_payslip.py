# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

import pytz

from odoo import api, fields, models
from odoo.fields import Domain


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    planning_slot_count = fields.Integer(compute='_compute_planning_slot_count', groups="planning.group_planning_manager")

    @api.depends('date_from', 'date_to', 'version_id')
    def _compute_planning_slot_count(self):
        self.planning_slot_count = 0
        planning_slips = self.filtered(lambda p: p.version_id.work_entry_source == 'planning')
        if not planning_slips:
            return
        domains = []
        slip_by_employee = defaultdict(lambda: self.env['hr.payslip'])
        for slip in planning_slips:
            slip_by_employee[slip.employee_id.id] |= slip
            domains.append([
                ('employee_id', '=', slip.employee_id.id),
                ('start_datetime', '<=', slip.date_to),
                ('end_datetime', '>=', slip.date_from),
            ])
        domain = Domain('state', '=', 'published') & Domain.OR(domains)
        read_group = self.env['planning.slot']._read_group(domain, groupby=['employee_id', 'start_datetime:day'], aggregates=['__count'])
        for employee, start_datetime_utc, count in read_group:
            slips = slip_by_employee[employee.id]
            start_date_employee = start_datetime_utc.astimezone(pytz.timezone(employee.tz)).date()
            for slip in slips:
                if slip.date_from <= start_date_employee and start_date_employee <= slip.date_to:
                    slip.planning_slot_count += count

    def action_open_planning_slots(self):
        self.ensure_one()
        action = self.employee_id.action_view_planning()
        action['domain'] = Domain.AND([
            action['domain'],
            [
                ('state', '=', 'published'),
                ('start_datetime', '<=', self.date_to),
                ('end_datetime', '>=', self.date_from),
            ],
        ])
        action['context']['default_scale'] = 'month'
        return action
