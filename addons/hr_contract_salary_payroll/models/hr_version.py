# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

from datetime import datetime, time


class HrVersion(models.Model):
    _inherit = 'hr.version'

    wage_with_holidays = fields.Monetary(groups="hr_payroll.group_hr_payroll_user")
    wage_on_signature = fields.Monetary(groups="hr_payroll.group_hr_payroll_user")
    final_yearly_costs = fields.Monetary(groups="hr_payroll.group_hr_payroll_user")
    monthly_yearly_costs = fields.Monetary(groups="hr_payroll.group_hr_payroll_user")
    salary_offer_ids = fields.One2many(groups="hr_payroll.group_hr_payroll_manager")

    # DO NOT CALL THIS FUNCTION OUTSIDE OF A ROLLBACK SAVEPOINT
    def _generate_salary_simulation_payslip(self):
        self.ensure_one()
        payslip = self.env['hr.payslip'].sudo().create({
            'employee_id': self.employee_id.id,
            'version_id': self.id,
            'struct_id': self.structure_type_id.default_struct_id.id,
            'company_id': self.employee_id.company_id.id,
            'name': 'Payslip Simulation',
        })

        # For hourly wage contracts generate the worked_days_line_ids manually
        if self.wage_type == 'hourly':
            work_days_data = self.employee_id._get_work_days_data_batch(
                datetime.combine(payslip.date_from, time.min), datetime.combine(payslip.date_to, time.max),
                compute_leaves=False, calendar=self.resource_calendar_id,
            )[self.employee_id.id]
            payslip.worked_days_line_ids = self.env['hr.payslip.worked_days'].with_context(salary_simulation=True).sudo().create({
                'payslip_id': payslip.id,
                'work_entry_type_id': self._get_default_work_entry_type_id(),
                'number_of_days': work_days_data.get('days', 0),
                'number_of_hours': work_days_data.get('hours', 0),
            })

        # Part Time Simulation
        old_wage_on_payroll = payslip.version_id.wage_on_signature
        old_wage = payslip.version_id.wage
        new_payslip_vals = {}
        if self.env.context.get("simulation_working_schedule"):
            working_schedule = self.env.context.get("simulation_working_schedule", '100')
            old_calendar = payslip.version_id.company_id.resource_calendar_id
            if working_schedule == '100':
                pass
            elif working_schedule == '90':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                if not new_calendar.two_weeks_calendar:
                    new_calendar.switch_calendar_type()
                new_calendar.attendance_ids.filtered(lambda a: a.day_period != 'lunch')[:2].unlink()
            elif working_schedule == '80':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                if new_calendar.two_weeks_calendar:
                    new_calendar.switch_calendar_type()
                new_calendar.attendance_ids.filtered(lambda a: a.day_period != 'lunch')[:2].unlink()
            elif working_schedule == '60':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                if new_calendar.two_weeks_calendar:
                    new_calendar.switch_calendar_type()
                new_calendar.attendance_ids.filtered(lambda a: a.day_period != 'lunch')[:4].unlink()
            elif working_schedule == '50':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                if new_calendar.two_weeks_calendar:
                    new_calendar.switch_calendar_type()
                new_calendar.attendance_ids.filtered(lambda a: a.day_period != 'lunch')[:5].unlink()
            elif working_schedule == '40':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                if new_calendar.two_weeks_calendar:
                    new_calendar.switch_calendar_type()
                new_calendar.attendance_ids.filtered(lambda a: a.day_period != 'lunch')[:6].unlink()
            elif working_schedule == '20':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                if new_calendar.two_weeks_calendar:
                    new_calendar.switch_calendar_type()
                new_calendar.attendance_ids.filtered(lambda a: a.day_period != 'lunch')[:8].unlink()
            new_wage_on_payroll = old_wage_on_payroll * int(working_schedule) / 100.0
            new_wage = old_wage * int(working_schedule) / 100.0
            is_full_time = working_schedule == '100'
            new_payslip_vals.update({
                'resource_calendar_id': new_calendar.id,
                'wage_on_signature': new_wage_on_payroll,
                'wage': new_wage,
            })

        else:
            work_time_rate = payslip.version_id.work_time_rate
            new_wage_on_payroll = old_wage_on_payroll * work_time_rate
            new_wage = old_wage * work_time_rate
            is_full_time = work_time_rate == 1.0
            new_payslip_vals.update({
                'wage_on_signature': new_wage_on_payroll,
                'wage': new_wage,
            })

        payslip = payslip.with_context(
            salary_simulation=True,
            salary_simulation_full_time=is_full_time,
            salary_simulation_full_time_wage_on_holidays=self.wage_with_holidays,
            salary_simulation_full_time_yearly_cost=self.final_yearly_costs,
            origin_version_id=self.env.context.get('origin_version_id', False),
            lang=None
        )

        if not is_full_time:
            payslip.version_id.write(new_payslip_vals)

        payslip.compute_sheet()
        return payslip
