# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.depends('is_paid', 'number_of_hours', 'payslip_id', 'version_id.wage', 'version_id.l10n_lu_indexed_wage', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        lu_worked_days = self.filtered(lambda wd: wd.payslip_id.struct_id.country_id.code == "LU")
        for worked_days in lu_worked_days:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state != 'draft':
                continue
            if not worked_days.version_id or worked_days.code == 'OUT':
                worked_days.amount = 0
                continue
            amount_rate = worked_days.work_entry_type_id.amount_rate
            attendance_hours = sum(
                wd.number_of_hours for wd in worked_days.payslip_id.worked_days_line_ids
                if not wd.work_entry_type_id.is_extra_hours
            ) or 1
            if worked_days.payslip_id.version_id.wage_type == "monthly":
                hourly_rate = worked_days.payslip_id.l10n_lu_prorated_wage / attendance_hours
            else:
                hourly_rate = worked_days.version_id.l10n_lu_indexed_wage
            worked_days.amount = hourly_rate * worked_days.number_of_hours * amount_rate if worked_days.is_paid else 0
        return super(HrPayslipWorkedDays, self - lu_worked_days)._compute_amount()
