# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    def _is_half_day(self):
        self.ensure_one()
        work_entry_type_overtime = self.env.ref('hr_work_entry.work_entry_type_overtime')
        if self.work_entry_type_id == work_entry_type_overtime:
            return False
        return super()._is_half_day()
