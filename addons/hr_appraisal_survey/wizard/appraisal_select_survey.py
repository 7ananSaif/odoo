# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AppraisalSelectSurvey(models.TransientModel):
    _name = 'appraisal.select.survey'
    _description = "Select survey type for an appraisal to show its results"

    survey_input_ids = fields.Many2many("survey.user_input", string="Survey Inputs", required=True)
    allowed_survey_template_ids = fields.Many2many('survey.survey', compute='_compute_allowed_survey_template_ids')
    survey_template_id = fields.Many2one('survey.survey', string="Survey", required=True,
                                         compute='_compute_survey_template_id', compute_sudo=False, store=True,
                                         readonly=False, domain="[('id', 'in', allowed_survey_template_ids)]")

    @api.depends('survey_input_ids')
    def _compute_allowed_survey_template_ids(self):
        for wizard in self:
            wizard.allowed_survey_template_ids = wizard.survey_input_ids.survey_id

    @api.depends('allowed_survey_template_ids')
    def _compute_survey_template_id(self):
        for wizard in self:
            if not wizard.survey_template_id:
                wizard.survey_template_id = wizard.allowed_survey_template_ids[:1]

    def action_see_results(self):
        self.ensure_one()
        return self.survey_input_ids.filtered(
            lambda s: s.survey_id == self.survey_template_id).action_open_all_survey_inputs()
