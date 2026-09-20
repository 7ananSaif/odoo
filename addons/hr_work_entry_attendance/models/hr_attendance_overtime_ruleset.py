# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrAttendanceOvertimeRuleset(models.Model):
    _name = 'hr.attendance.overtime.ruleset'
    _inherit = 'hr.attendance.overtime.ruleset'

    def _attendances_to_regenerate_for(self):
        attendances = super()._attendances_to_regenerate_for()
        with_validated_work_entry = self.env['hr.work.entry']._read_group([
                ('attendance_id', 'in', attendances.ids),
                ('state', '=', 'validated'),
            ],
            groupby=[],
            aggregates=['attendance_id:recordset'],
        )[0][0]
        return attendances - with_validated_work_entry
