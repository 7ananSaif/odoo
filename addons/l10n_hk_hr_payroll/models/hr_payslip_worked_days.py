# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    l10n_hk_leave_id = fields.Many2one('hr.leave', string='Leave', readonly=True)

    @api.depends('is_paid', 'number_of_hours', 'payslip_id', 'version_id', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        hk_worked_days = self.filtered(lambda wd: wd.payslip_id.struct_id.country_id.code == "HK")

        for worked_days in hk_worked_days:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state != 'draft':
                continue
            if not worked_days.version_id or worked_days.code == 'OUT' or not worked_days.is_paid:
                worked_days.amount = 0
                continue
            amount_rate = worked_days.work_entry_type_id.amount_rate
            if worked_days.payslip_id.wage_type == "hourly":
                hourly_wage = worked_days.payslip_id.version_id.hourly_wage
                if worked_days.work_entry_type_id.l10n_hk_use_713:
                    hourly_wage = worked_days.payslip_id.l10n_hk_average_daily_wage / worked_days.version_id.resource_calendar_id.hours_per_day
                worked_days.amount = hourly_wage * worked_days.number_of_hours * amount_rate
            else:
                payslip = worked_days.payslip_id
                if worked_days.l10n_hk_leave_id:
                    payslip = self.env['hr.payslip'].search([
                        ('employee_id', '=', worked_days.payslip_id.employee_id.id),
                        ('date_from', '<=', worked_days.l10n_hk_leave_id.date_from),
                        ('date_to', '>=', worked_days.l10n_hk_leave_id.date_from),
                        ('state', 'in', ['validated', 'paid']),
                    ], limit=1) or worked_days.payslip_id
                attendance_hours = sum(
                    wd.number_of_hours for wd in payslip.worked_days_line_ids
                    if not wd.work_entry_type_id.is_extra_hours
                )
                sum_worked_days = attendance_hours / worked_days.version_id.resource_calendar_id.hours_per_day
                daily_wage = worked_days.version_id.contract_wage / (sum_worked_days or 1)
                if worked_days.work_entry_type_id.l10n_hk_use_713:
                    daily_wage = payslip.l10n_hk_average_daily_wage
                number_of_days = worked_days.number_of_hours / worked_days.version_id.resource_calendar_id.hours_per_day
                worked_days.amount = daily_wage * number_of_days * amount_rate

        super(HrPayslipWorkedDays, self - hk_worked_days)._compute_amount()
