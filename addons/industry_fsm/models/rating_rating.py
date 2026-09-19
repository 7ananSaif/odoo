from odoo import api, fields, models


class RatingRating(models.Model):
    _inherit = 'rating.rating'

    project_id = fields.Many2one("project.project", compute="_compute_project_id", search='_search_project_id')

    @api.depends('parent_res_model', 'parent_res_id')
    def _compute_project_id(self):
        if project_ratings := self.filtered(lambda r: r.parent_res_model == 'project.project' and r.parent_res_id):
            projects = self.env['project.project'].search([('id', 'in', project_ratings.mapped('parent_res_id'))])
            project_map = {project.id: project for project in projects}
            for project_rating in project_ratings:
                project_rating.project_id = project_map.get(project_rating.parent_res_id, False)
        (self - project_ratings).project_id = False

    def _search_project_id(self, operator, value):
        projects = self.env['project.project'].search([('id', operator, value)])
        return [('parent_res_model', '=', 'project.project'), ('parent_res_id', 'in', projects.ids)]
