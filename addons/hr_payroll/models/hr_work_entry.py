# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import datetime, date, time
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'
    has_payslip = fields.Boolean(compute='_compute_has_payslip')

    @api.depends('state')
    def _compute_has_payslip(self):
        all_payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', self.employee_id.ids),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '<=', max(self.mapped('date'))),
            ('date_to', '>=', min(self.mapped('date'))),
        ])

        for work_entry in self:
            work_entry.has_payslip = any(
                slip.employee_id == work_entry.employee_id
                and slip.date_from <= work_entry.date <= slip.date_to
                and not slip.is_refunded
                for slip in all_payslips)

    def _check_undefined_slots(self, interval_start, interval_end):
        """
        Check if a time slot in the given interval is not covered by a work entry
        """
        work_entries_by_contract = defaultdict(lambda: self.env['hr.work.entry'])
        for work_entry in self:
            work_entries_by_contract[work_entry.version_id] |= work_entry

        for contract, work_entries in work_entries_by_contract.items():
            if contract.work_entry_source != 'calendar':
                continue
            tz = pytz.timezone(contract.resource_calendar_id.tz)
            calendar_start = tz.localize(datetime.combine(max(contract.date_start, interval_start), time.min))
            calendar_end = tz.localize(datetime.combine(min(contract.date_end or date.max, interval_end), time.max))
            outside = contract.resource_calendar_id._attendance_intervals_batch(calendar_start, calendar_end)[False] - work_entries._to_intervals()
            if outside:
                time_intervals_str = "\n - ".join(['', *["%s -> %s" % (s[0], s[1]) for s in outside._items]])
                employee_name = contract.employee_id.name
                msg = _("Watch out for gaps in %(employee_name)s's calendar\n\nPlease complete the missing work entries of %(employee_name)s:%(time_intervals_str)s "
                    "\n\nMissing work entries are like the Bermuda Triangle for paychecks. Let's keep your colleague's earnings from vanishing into thin air!"
                    , employee_name=employee_name, time_intervals_str=time_intervals_str)
                raise UserError(msg)

    def action_set_to_draft(self):
        return self.write({'state': 'draft'})

    def write(self, vals):
        if vals.get('state') == 'conflict' or ('active' in vals and vals['active'] is False):
            return super().write(vals)
        for work_entry in self:
            if work_entry.state == 'validated' and not vals.get('state'):
                raise UserError(_("This work entry cannot be modified because it is already associated with a generated payslip."))
        return super().write(vals)
