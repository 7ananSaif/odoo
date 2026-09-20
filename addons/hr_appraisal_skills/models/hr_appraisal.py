# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, Command, fields, models
from odoo.tools import convert


class HrAppraisal(models.Model):
    _inherit = 'hr.appraisal'

    target_job_id = fields.Many2one('hr.job')
    appraisal_skill_ids = fields.One2many('hr.appraisal.skill', 'appraisal_id', string="Skills",
        domain=['|', ('skill_type_id.active', '=', True), ('appraisal_id.state', '=', '3_done')],
        compute="_compute_appraisal_skill_ids", store=True, readonly=False)
    current_appraisal_skill_ids = fields.One2many('hr.appraisal.skill', 'appraisal_id', compute='_compute_current_appraisal_skill_ids', readonly=False)

    @api.depends('appraisal_skill_ids')
    def _compute_current_appraisal_skill_ids(self):
        for appraisal in self:
            appraisal.current_appraisal_skill_ids = appraisal.appraisal_skill_ids.filtered(
                lambda appraisal_skill: appraisal_skill.is_certification or
                    not appraisal_skill.valid_to or appraisal_skill.valid_to >= fields.Date.today()
            )

    @api.depends('target_job_id')
    def _compute_appraisal_skill_ids(self):
        for appraisal in self:
            values = [
                Command.unlink(appraisal_skill.id)
                for appraisal_skill in appraisal.appraisal_skill_ids.filtered(
                    lambda skill: not skill.skill_level_id
                )
            ]
            target_job_current_skills = appraisal.target_job_id.current_job_skill_ids
            current_skills = appraisal.appraisal_skill_ids.filtered(
                lambda appraisal_skill: (appraisal_skill.is_certification or
                    not appraisal_skill.valid_to or appraisal_skill.valid_to >= fields.Date.today())
                    and appraisal_skill.skill_level_id
            )
            new_skills_ids = (target_job_current_skills.skill_id - current_skills.skill_id).ids
            if new_skills_ids:
                values += [Command.create({
                    'skill_id': job_skill.skill_id.id,
                    'skill_type_id': job_skill.skill_type_id.id,
                    'skill_level_id': False,
                    'valid_from': fields.Date.today(),
                    'valid_to': False,
                    'appraisal_id': appraisal._origin.id,  # need to understand why .id was a newId
                }) for job_skill in target_job_current_skills.filtered(lambda skill: skill.skill_id.id in new_skills_ids)]
            if values:
                appraisal.write({'appraisal_skill_ids': values})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "current_appraisal_skill_ids" in vals:
                vals_app_skill = vals.pop('current_appraisal_skill_ids')
                vals['appraisal_skill_ids'] = self.env['hr.appraisal.skill']._get_transformed_commands(vals_app_skill, self)
        res = super().create(vals_list)
        return res

    def write(self, vals):
        if "current_appraisal_skill_ids" in vals:
            vals_app_skill = vals.pop('current_appraisal_skill_ids')
            vals['appraisal_skill_ids'] = self.env['hr.appraisal.skill']._get_transformed_commands(vals_app_skill, self)

        if 'state' in vals and vals['state'] == '2_pending':
            new_appraisals = self.filtered(lambda a: a.state == '1_new')
            new_appraisals._copy_skills_when_confirmed()

        if 'state' in vals and (vals['state'] == '3_done'):
            for appraisal in self:
                employee_skills = appraisal.employee_id.current_employee_skill_ids
                # Remove skills created by target without any changes
                appraisal_skills = appraisal.current_appraisal_skill_ids.filtered('skill_level_id')
                updated_skills = []
                deleted_skills_name = []
                added_skills = []
                for employee_skill in employee_skills.filtered(lambda s: s.skill_id in appraisal_skills.skill_id):
                    appraisal_skill = appraisal_skills.filtered(lambda a: a.skill_id == employee_skill.skill_id)
                    if employee_skill.level_progress != appraisal_skill.level_progress:
                        updated_skills.append({
                            'name': employee_skill.skill_id.name,
                            'old_level': employee_skill.level_progress,
                            'new_level': appraisal_skill.level_progress,
                            'justification': appraisal_skill.justification,
                        })

                deleted_skills = employee_skills.filtered(lambda s: s.skill_id not in appraisal_skills.skill_id)
                deleted_skills_name = deleted_skills.mapped('skill_id.name')
                added_skills = appraisal_skills.filtered(lambda a: a.skill_id not in employee_skills.skill_id).mapped('skill_id.name')

                appraisal.employee_id.sudo().write({
                    'employee_skill_ids': [[0, 0, {
                        'employee_id': appraisal.employee_id.id,
                        'skill_id': skill.skill_id.id,
                        'skill_level_id': skill.skill_level_id.id,
                        'skill_type_id': skill.skill_type_id.id,
                        'valid_from': skill.valid_from if skill.is_certification else fields.Date.today(),
                        'valid_to': skill.valid_to if skill.is_certification else False,
                    }] for skill in appraisal_skills] + [[2, skill.id] for skill in deleted_skills]
                })

                if len(updated_skills + added_skills + deleted_skills_name) > 0:
                    rendered = self.env['ir.qweb']._render('hr_appraisal_skills.appraisal_skills_update_template', {
                        'updated_skills': updated_skills,
                        'added_skills': added_skills,
                        'deleted_skills': deleted_skills_name,
                    }, raise_if_not_found=False)
                    appraisal.message_post(body=rendered)
        result = super().write(vals)
        return result

    def _copy_skills_when_confirmed(self):
        vals = []
        for appraisal in self:
            employee_skills = appraisal.employee_id.current_employee_skill_ids
            # in case the employee confirms its appraisal
            if appraisal.appraisal_skill_ids:  # check in case we are coming from a previously canceled appraisal and recreate them
                appraisal.appraisal_skill_ids.unlink()
            vals += [{
                'appraisal_id': appraisal.id,
                'skill_id': skill.skill_id.id,
                'previous_skill_level_id': skill.skill_level_id.id,
                'skill_level_id': skill.skill_level_id.id,
                'skill_type_id': skill.skill_type_id.id,
                'valid_from': skill.valid_from,
                'valid_to': skill.valid_to
            } for skill in employee_skills]
        self.env['hr.appraisal.skill'].sudo().create(vals)

    def _load_demo_data(self):
        super()._load_demo_data()
        convert.convert_file(self.env, 'hr_appraisal_skills', 'demo/scenarios/scenario_appraisal_demo.xml', None, mode='init')
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
