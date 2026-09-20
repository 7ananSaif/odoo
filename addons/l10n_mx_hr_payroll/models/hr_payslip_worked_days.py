# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.depends('is_paid', 'number_of_hours', 'payslip_id', 'version_id.wage', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        mx_worked_days = self.filtered(lambda wd: wd.payslip_id.struct_id.country_id.code == "MX")
        for worked_days in mx_worked_days:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state != 'draft':
                continue
            if not worked_days.version_id or worked_days.code == 'OUT':
                worked_days.amount = 0
                continue
            if not worked_days.payslip_id.date_from or not worked_days.payslip_id.date_to:
                continue

            start_date = max(worked_days.payslip_id.date_from, worked_days.version_id.contract_date_start or worked_days.version_id.date_version)
            end_date = min(worked_days.payslip_id.date_to, worked_days.version_id.contract_date_end) if worked_days.version_id.contract_date_end else worked_days.payslip_id.date_to
            in_contract_days = (end_date - start_date).days + 1
            actual_period_days = (worked_days.payslip_id.date_to - worked_days.payslip_id.date_from).days + 1
            salary_factor = in_contract_days / actual_period_days

            period_wage = worked_days._get_period_wage()
            amount_rate = worked_days.work_entry_type_id.amount_rate
            worked_days.amount = period_wage * salary_factor * amount_rate
        return super(HrPayslipWorkedDays, self - mx_worked_days)._compute_amount()

    def _get_period_wage(self):
        self.ensure_one()
        if not self.is_paid:
            return 0
        if self.version_id.wage_type == 'hourly':
            return self.version_id.hourly_wage * self.number_of_hours
        else:
            attendance_hours = sum(
                line.number_of_hours for line in self.payslip_id.worked_days_line_ids
                if line.code != 'OUT' and not line.work_entry_type_id.is_extra_hours
            ) or 1
            return self.version_id.wage * self.number_of_hours / attendance_hours
