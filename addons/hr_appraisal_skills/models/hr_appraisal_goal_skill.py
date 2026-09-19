# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrAppraisalGoalSkill(models.Model):
    _name = "hr.appraisal.goal.skill"
    _inherit = "hr.individual.skill.mixin"
    _description = "Skills for goal positions"
    _order = "skill_type_id, skill_level_id desc"
    _rec_name = "skill_id"

    goal_id = fields.Many2one(
        comodel_name="hr.appraisal.goal",
        required=True,
        index=True,
        ondelete="cascade",
    )

    def _linked_field_name(self):
        return "goal_id"
