# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class HrAppraisalSkill(models.Model):
    _name = 'hr.appraisal.skill'
    _inherit = 'hr.individual.skill.mixin'
    _description = "Appraisal Skills"
    _order = "skill_type_id, skill_level_id"

    appraisal_id = fields.Many2one('hr.appraisal', required=True, ondelete='cascade')
    skill_level_id = fields.Many2one('hr.skill.level', required=False)  # To handle Target Job
    employee_id = fields.Many2one(related="appraisal_id.employee_id", store=True)
    previous_skill_level_id = fields.Many2one('hr.skill.level')
    justification = fields.Char()
    manager_ids = fields.Many2many('hr.employee', compute='_compute_manager_ids', store=True)
    goal_ids = fields.Many2many('hr.appraisal.goal', compute='_compute_goal_ids', store=True)
    goals_completion_percentage = fields.Integer(compute='_compute_goals_completion_percentage', string="Current Goals", store=True)
    number_of_recommended_goals = fields.Integer(compute='_compute_number_of_recommended_goals')
    target_job_skill_progress = fields.Float(compute="_compute_target_job_skill_progress", store=True, string="Job Target")

    _target_job_skill_progress_range = models.Constraint(
        'check(target_job_skill_progress >= 0 and target_job_skill_progress <= 1)',
        'Job Target Score should be between 0 and 1',
    )
    _check_goals_completion_percentage = models.Constraint(
        'CHECK(goals_completion_percentage BETWEEN 0 AND 100)',
        'Progress should be a number between 0 and 100.',
    )

    def _linked_field_name(self):
        return 'appraisal_id'

    def _get_passive_fields(self):
        return ["justification"]

    @api.constrains('skill_type_id', 'skill_level_id')
    def _check_skill_level(self):
        for record in self:
            if record.skill_level_id and record.skill_level_id not in record.skill_type_id.skill_level_ids:
                raise ValidationError(self.env._("The skill level %(level)s is not valid for skill type: %(type)s",
                    level=record.skill_level_id.name, type=record.skill_type_id.name))

    @api.depends('skill_id', 'appraisal_id.target_job_id.current_job_skill_ids')
    def _compute_target_job_skill_progress(self):
        appraisal_skill_by_appraisal = self.grouped('appraisal_id')
        for appraisal, appraisal_skills in appraisal_skill_by_appraisal.items():
            target_job_skills_by_skill = appraisal.target_job_id.current_job_skill_ids.grouped('skill_id')  # at most one current job skill per skill
            for app_skill in appraisal_skills:
                target_job_skill = target_job_skills_by_skill.get(app_skill.skill_id, False)
                if target_job_skill:
                    app_skill.target_job_skill_progress = target_job_skill.level_progress / 100
                else:
                    app_skill.target_job_skill_progress = False

    @api.depends('appraisal_id.manager_ids')
    def _compute_manager_ids(self):
        for appraisal_skill in self:
            appraisal_skill.manager_ids = appraisal_skill.appraisal_id.manager_ids

    @api.depends('skill_id', 'skill_level_id')
    def _compute_display_name(self):
        for individual_skill in self:
            skill_level_name = individual_skill.skill_level_id.name if individual_skill.skill_level_id else self.env._("Unknown")
            individual_skill.display_name = f"{individual_skill.skill_id.name}: {skill_level_name}"

    @api.depends('employee_id.goals_ids')
    def _compute_goal_ids(self):
        goals = self.env['hr.appraisal.goal'].search([
            ('employee_ids', 'in', self.employee_id.ids),
            ('child_ids', '=', False),
            ('current_goal_skill_ids.skill_id', 'in', self.skill_id.ids),
        ])
        goals_by_skill = defaultdict(lambda: self.env['hr.appraisal.goal'])
        for goal in goals:
            for skill in goal.current_goal_skill_ids:
                goals_by_skill[skill.skill_id.id] += goal
        for skill in self:
            skill.goal_ids = goals_by_skill[skill.skill_id.id]

    @api.depends('goal_ids.progression')
    def _compute_goals_completion_percentage(self):
        for skill in self:
            if not skill.goal_ids:
                skill.goals_completion_percentage = 0
                continue
            completed_goals = skill.goal_ids.filtered(lambda goal: goal.progression == '100')
            skill.goals_completion_percentage = 100 * len(completed_goals.ids) / len(skill.goal_ids.ids)

    @api.depends('skill_id', 'level_progress', 'goal_ids')
    def _compute_number_of_recommended_goals(self):
        nb_goals_skill_by_skill_by_level = {
            (skill, level): goal_skills
            for skill, level, goal_skills in self.env['hr.appraisal.goal.skill']._read_group(
                domain=Domain.AND([
                    Domain('goal_id', 'any', Domain.AND([
                        Domain('employee_ids', '=', False),
                        Domain('id', 'not in', self.employee_id.sudo().goals_ids.template_goal_id.ids)
                    ])),
                    Domain.OR([
                        Domain.AND([
                            Domain('skill_id', '=', appraisal_skill.skill_id.id),
                            Domain('level_progress', '>', appraisal_skill.level_progress),
                        ])
                    ] for appraisal_skill in self)
                ]),
                groupby=['skill_id', 'skill_level_id'],
                aggregates=['__count'],
            )}
        for appraisal_skill in self:
            higher_or_equal_levels = appraisal_skill.skill_type_id.skill_level_ids.filtered(
                lambda level: level.level_progress > appraisal_skill.level_progress
            )
            appraisal_skill.number_of_recommended_goals = sum(
                nb_goals_skill_by_skill_by_level.get((appraisal_skill.skill_id, level), 0)
            for level in higher_or_equal_levels)

    def action_open_recommend_goals(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_appraisal.action_hr_appraisal_goal_template_library')
        action['context'] = {'default_employee_id': self.employee_id.id}
        action['domain'] = Domain.AND([
            Domain('employee_ids', '=', False),
            Domain('id', 'not in', self.employee_id.sudo().goals_ids.template_goal_id.ids),
            Domain('current_goal_skill_ids', 'any',
                Domain.AND([
                    Domain('skill_id', '=', self.skill_id.id),
                    Domain('level_progress', '>', self.level_progress),
                ])
            ),
        ])
        return action

    def action_open_current_goals(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_appraisal.action_hr_appraisal_goal')
        action['domain'] = Domain('id', 'in', self.goal_ids.ids)
        action['context'] = {'create': False}
        if len(self.goal_ids.ids) == 1:
            action['view_mode'] = 'form'
            action['views'] = [(self.env.ref('hr_appraisal.hr_appraisal_goal_view_form').id, 'form')]
            action['res_id'] = self.goal_ids.id
        return action
