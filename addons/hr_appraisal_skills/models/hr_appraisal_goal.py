# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, Command

from odoo.fields import Domain


class HrAppraisalGoal(models.Model):
    _inherit = 'hr.appraisal.goal'

    goal_skill_ids = fields.One2many(
        comodel_name="hr.appraisal.goal.skill",
        inverse_name="goal_id",
        string="Skills",
        domain=[("skill_type_id.active", "=", True)],
    )
    current_goal_skill_ids = fields.One2many(
        comodel_name="hr.appraisal.goal.skill",
        compute="_compute_current_goal_skill_ids",
        search="_search_current_goal_skill_ids",
        help="This goal will be recommended to reach the level of those skills.",
        readonly=False,
    )

    @api.depends("goal_skill_ids")
    def _compute_current_goal_skill_ids(self):
        for goal in self:
            goal.current_goal_skill_ids = goal.goal_skill_ids.filtered(
                lambda goal_skill: not goal_skill.valid_to or goal_skill.valid_to >= fields.Date.today()
            )

    def _search_current_goal_skill_ids(self, operator, value):
        if operator not in ('in', 'not in', 'any'):
            raise NotImplementedError()
        goal_skill_ids = []
        domain = Domain.OR([
            Domain('valid_to', '=', False),
            Domain('valid_to', '>=', fields.Date.today()),
        ])
        if operator == 'any' and isinstance(value, Domain):
            domain = Domain.AND([domain, value])

        elif operator in ('in', 'not in'):
            domain = Domain.AND([domain, Domain('id', operator, value)])

        goal_skill_ids = self.env['hr.appraisal.goal.skill']._search(domain)
        return Domain('goal_skill_ids', 'in', goal_skill_ids)

    def _get_goals_values(self, employee_id, goal_parent_id):
        self.ensure_one()
        res = super()._get_goals_values(employee_id, goal_parent_id)
        # Need to use this method instead of copy because it's not possible to duplicate a hr.appraisal.goal.skill
        skill_values = self.current_goal_skill_ids.read(load=False)
        for skill_value in skill_values:
            skill_value['goal_id'] = False
        res.update({
            'goal_skill_ids': [Command.create(skill_value) for skill_value in skill_values]
        })
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "current_goal_skill_ids" in vals or "goal_skill_ids" in vals:
                vals_goal_skill = vals.pop("current_goal_skill_ids", []) + vals.get("goal_skill_ids", [])
                vals["goal_skill_ids"] = self.env["hr.appraisal.goal.skill"]._get_transformed_commands(
                    vals_goal_skill, self
                )
        return super().create(vals_list)

    def write(self, vals):
        if "current_goal_skill_ids" in vals or "goal_skill_ids" in vals:
            vals_goal_skill = vals.pop("current_goal_skill_ids", []) + vals.get("goal_skill_ids", [])
            vals["goal_skill_ids"] = self.env["hr.appraisal.goal.skill"]._get_transformed_commands(
                vals_goal_skill, self
            )
        return super().write(vals)

    def copy(self, default=None):
        new_goals = super().copy(default)

        new_goal_by_old_goal = dict(zip(self.ids, new_goals.ids))
        # Need to use this method instead of copy because it's not possible to duplicate a hr.appraisal.goal.skill
        new_skill_values = self.goal_skill_ids.read(load=False)

        for new_skill_value in new_skill_values:
            old_goal_id = new_skill_value['goal_id']
            new_skill_value['goal_id'] = new_goal_by_old_goal[old_goal_id]

        self.env['hr.appraisal.goal.skill'].create(new_skill_values)
        return new_goals
