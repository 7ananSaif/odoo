# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import date
import calendar

from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_mx_daily_salary = fields.Float('MX: Daily Salary', compute='_compute_daily_salary')
    l10n_mx_years_worked = fields.Integer('MX: Years Worked', compute='_compute_integration_factor')
    l10n_mx_days_of_year = fields.Integer('MX: Days of the Year', compute='_compute_days_of_year')
    l10n_mx_integration_factor = fields.Float('MX: Integration Factor', compute='_compute_integration_factor')

    @api.depends('version_id.wage', 'version_id.schedule_pay')
    def _compute_daily_salary(self):
        for payslip in self:
            payslip.l10n_mx_daily_salary = payslip.version_id.wage / payslip._rule_parameter('l10n_mx_schedule_table')[payslip.version_id.schedule_pay]

    @api.depends('date_to')
    def _compute_days_of_year(self):
        for payslip in self:
            year = payslip.date_to.year
            payslip.l10n_mx_days_of_year = (date(year, 12, 31) - date(year, 1, 1)).days + 1

    @api.depends('l10n_mx_days_of_year', 'date_from', 'date_to', 'version_id')
    def _compute_integration_factor(self):
        for payslip in self:
            start_date = payslip.employee_id.contract_date_start
            payslip.l10n_mx_years_worked = payslip.date_to.year - start_date.year
            if start_date <= payslip.date_to + relativedelta(year=start_date.year):
                payslip.l10n_mx_years_worked += 1
            holidays_count = payslip._rule_parameter('l10n_mx_holiday_tables')[payslip.l10n_mx_years_worked]
            holiday_bonus_factor = holidays_count * payslip.version_id.l10n_mx_holiday_bonus_rate / 100

            number_of_days_year = payslip.l10n_mx_days_of_year
            payslip.l10n_mx_integration_factor = (holiday_bonus_factor + payslip._rule_parameter('l10n_mx_christmas_bonus') + number_of_days_year) / number_of_days_year

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_mx_hr_payroll', [
                'data/hr_salary_rule_category_data.xml',
                'data/hr_payroll_structure_type_data.xml',
                'data/hr_payroll_structure_data.xml',
                'data/hr_rule_parameters_data.xml',
                'data/salary_rules/hr_salary_rule_christmas_bonus_data.xml',
                'data/salary_rules/hr_salary_rule_regular_pay_data.xml',
            ])]

    def _get_schedule_timedelta(self):
        if self.country_code == 'MX':

            if self.struct_id.code == "MX_REGULAR":
                schedule = self.version_id.schedule_pay
                if schedule == '10_days':
                    return relativedelta(days=9)
                elif schedule == '14_days':
                    return relativedelta(days=13)
                elif schedule == 'bi-weekly':
                    days_in_month = calendar.monthrange(self.date_from.year, self.date_from.month)[1]
                    return relativedelta(day=15 if self.date_from.day <= 15 else days_in_month)
                elif schedule == 'bi-monthly':
                    return relativedelta(months=2, days=-1)

            elif self.struct_id.code in ["MX_CHRISTMAS", "MX_PTU"]:
                return relativedelta(day=31, month=12)

        return super()._get_schedule_timedelta()
