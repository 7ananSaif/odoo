# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from random import randint

from odoo import fields
from odoo.fields import Datetime
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


def _generate_payslips(env):
    # Do this only when demo data is activated
    if env.ref('base.demo_company_be', raise_if_not_found=False):
        if not env['hr.payslip'].sudo().search_count([('employee_id.name', '=', 'Marian Weaver')]):
            _logger.info('Generating payslips')
            joseph = env.ref('test_l10n_be_hr_payroll_account.hr_employee_joseph_noluck', raise_if_not_found=False)
            if not joseph:
                return
            employees = env['hr.employee'].search([
                ('company_id', '=', env.ref('base.demo_company_be').id),
                ('id', '!=', joseph.id),
            ])
            # Everyone was on training 1 week
            leaves = env['hr.leave']
            training_type = env.ref('test_l10n_be_hr_payroll_account.l10n_be_leave_type_training')
            for employee in employees:
                training_leave = env['hr.leave'].new({
                    'name': 'Whole Company Training',
                    'employee_id': employee.id,
                    'holiday_status_id': training_type.id,
                    'request_date_from': fields.Date.today() + relativedelta(day=1, month=1, years=-1),
                    'request_date_to': fields.Date.today() + relativedelta(day=7, month=1, years=-1),
                    'request_hour_from': 7,
                    'request_hour_to': 18,
                    'number_of_days': 5,
                })
                training_leave._compute_date_from_to()
                leaves |= env['hr.leave'].create(training_leave._convert_to_write(training_leave._cache))
            env['hr.leave'].search([]).write({'payslip_state': 'done'})  # done or normal : to check!!!

            cids = env.ref('base.demo_company_be').ids
            payslip_runs = env['hr.payslip.run']
            payslis_values = []
            for i in range(2, 20):
                date_start = Datetime.today() - relativedelta(months=i, day=1)
                date_end = Datetime.today() - relativedelta(months=i, day=31)
                payslis_values.append({
                    'name': date_start.strftime('%B %Y'),
                    'date_start': date_start,
                    'date_end': date_end,
                    'company_id': env.ref('base.demo_company_be').id,
                    'structure_id': env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
                })
            payslip_runs = env['hr.payslip.run'].create(payslis_values)
            for payslip_run in payslip_runs:
                payslip_run.generate_payslips(employee_ids=[employee.id for employee in employees])
            _logger.info('Validating payslips')
            # after many insertions in work_entries, table statistics may be broken.
            # In this case, query plan may be randomly suboptimal leading to slow search
            # Analyzing the table is fast, and will transform a potential ~30 seconds
            # sql time for _mark_conflicting_work_entries into ~2 seconds
            env.cr.execute('ANALYZE hr_work_entry')
            payslip_runs.with_context(allowed_company_ids=cids).action_validate()

        # Generate skills logs
        employee_skills_vals = []
        data_vals = []
        today = fields.Date.today()
        all_skills = env['hr.skill'].search([])
        regular_skills = all_skills.filtered(lambda skill: not skill.skill_type_id.is_certification)
        all_belgium_employees = env['hr.employee'].search([('company_id', '=', env.ref('base.demo_company_be').id)])
        # To unlink expired one and expire no expired one
        env['hr.employee.skill'].search([('employee_id.company_id', '=', env.ref('base.demo_company_be').id)]).unlink()
        # To unlink new expired one
        env['hr.employee.skill'].search([('employee_id.company_id', '=', env.ref('base.demo_company_be').id)]).unlink()
        for employee in all_belgium_employees:
            for skill in regular_skills:
                if randint(0, 100) > 90:
                    array = skill.skill_type_id.skill_level_ids.sorted('level_progress')
                    max_level_index = len(array) - 1
                    level_index = 0
                    skills_vals = []
                    for index in range(6):
                        if randint(1, 5) == 1 and level_index < max_level_index:
                            level_index = level_index + 1
                            if skills_vals:
                                skills_vals[-1]['valid_to'] = today + relativedelta(months=(index - 6 - 1) * 6, day=1)
                            skills_vals.append({
                                'employee_id': employee.id,
                                'skill_id': skill.id,
                                'skill_type_id': skill.skill_type_id.id,
                                'skill_level_id': array[level_index].id,
                                'valid_from': today + relativedelta(months=(index - 6 - 1) * 6, day=2),
                                'valid_to': False
                            })
                    employee_skills_vals = employee_skills_vals + skills_vals
            for skill in all_skills - regular_skills:
                if randint(1, 4) == 1:
                    number_of_certification = randint(1, 3)
                    has_no_valid_to = randint(1, 4) == 1
                    array = skill.skill_type_id.skill_level_ids.sorted('level_progress')
                    max_level_index = len(array) - 1
                    level_index = 0
                    for index in range(number_of_certification):
                        employee_skills_vals.append({
                            'employee_id': employee.id,
                            'skill_id': skill.id,
                            'skill_type_id': skill.skill_type_id.id,
                            'skill_level_id': array[level_index].id,
                            'valid_from': today + relativedelta(months=(index - number_of_certification - 1) * 6 + 2),
                            'valid_to': False if number_of_certification - 1 == index and has_no_valid_to else today + relativedelta(months=(index - number_of_certification) * 6 + 2, days=-1)
                        })
                        if randint(1, 4) == 1:
                            level_index = min(max_level_index, level_index + 1)
        employee_skills = env['hr.employee.skill'].create(employee_skills_vals)
        prefix = 'test_l10n_be_hr_payroll_account'
        for skill in employee_skills:
            employee_id = skill.employee_id.id
            skill_id = skill.skill_id.id
            level_id = skill.skill_level_id.id
            valid_from = skill.valid_from
            valid_to = skill.valid_to
            data_vals.append({
                'name': f'{prefix}.skill_employee_{employee_id}_skill_{skill_id}_level_{level_id}_{valid_from}_{valid_to}',
                'module': prefix,
                'res_id': skill.id,
                'model': 'hr.employee.skill',
                'noupdate': True,
            })

        env['ir.model.data'].create(data_vals)
