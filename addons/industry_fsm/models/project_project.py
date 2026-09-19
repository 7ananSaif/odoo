# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.fields import Command, Domain


class ProjectProject(models.Model):
    _inherit = "project.project"

    is_fsm = fields.Boolean("Field Service", default=False, help="Display tasks in the Field Service module and allow planning with start/end dates.")
    allow_geolocation = fields.Boolean(
        "Geolocation",
        compute='_compute_allow_geolocation', store=True, readonly=False,
        help="Track technician location when running the timer.",
    )

    @api.depends('is_fsm', 'is_internal_project', 'company_id')
    @api.depends_context('allowed_company_ids')
    def _compute_display_name(self):
        super()._compute_display_name()
        if len(self.env.context.get('allowed_company_ids', [])) <= 1:
            return
        fsm_project_default_name = _("Field Service")
        for project in self:
            if project.is_fsm and project.name == fsm_project_default_name and not project.is_internal_project:
                project.display_name = f'{project.display_name} - {project.company_id.name}'

    _company_id_required_for_fsm_project = models.Constraint(
        "CHECK((is_fsm = 't' AND company_id IS NOT NULL) OR is_fsm = 'f')",
        "A fsm project must be company restricted",
    )

    @api.depends('is_fsm')
    def _compute_company_id(self):
        #The super() call is done first in order to set the company of the fsm projects to the company of its account if a company is set on it.
        super()._compute_company_id()
        fsm_projects = self.filtered(lambda project: project.is_fsm and not project.company_id)
        fsm_projects.company_id = self.env.company

    @api.depends('is_fsm', 'allow_timesheets')
    def _compute_allow_geolocation(self):
        for project in self:
            if not (project.is_fsm and project.allow_timesheets):
                project.allow_geolocation = False

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        if defaults.get('is_fsm', False) and not defaults.get('company_id', False):
            defaults['company_id'] = self.env.company.id
        return defaults

    def _get_projects_to_make_billable_domain(self):
        return Domain.AND([
            super()._get_projects_to_make_billable_domain(),
            [('is_fsm', '=', False)],
        ])

    @api.model
    def get_create_edit_project_ids(self):
        return self.env['project.project'].search([('is_fsm', '=', True)]).ids

    @api.model
    def _get_default_task_type_values(self):
        return [
            {'name': name, 'sequence': sequence, 'fold': fold, 'project_ids': False}
            for name, sequence, fold in [
                (_('New'), 1, False),
                (_('Planned'), 5, False),
                (_('In Progress'), 10, False),
                (_('Done'), 20, True),
                (_('Cancelled'), 25, True),
            ]
        ]

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        for project, vals in zip(self, vals_list):
            if self.env.context.get('copy_from_template') and self.env.context.get('default_is_fsm'):
                # For a FSM project to be created from template company_id is required constraint
                vals['company_id'] = self.env.context.get('default_company_id') or project.company_id.id or self.env.company.id
        return vals_list

    @api.model_create_multi
    def create(self, vals_list):
        fsm_vals_list = [vals for vals in vals_list if vals.get('is_fsm')]
        if fsm_vals_list:
            existing_fsm_project = self.env['project.project'].search(
                [('is_fsm', '=', True)],
                limit=1,
                order="sequence"
            )
            if not existing_fsm_project.type_ids:
                task_type_ids = self.env['project.task.type'].create(self._get_default_task_type_values()).ids
            else:
                task_type_ids = existing_fsm_project.type_ids.ids
            for vals in fsm_vals_list:
                vals.setdefault('type_ids', [(Command.set(task_type_ids))])
        return super().create(vals_list)

    def _get_template_default_context_whitelist(self):
        return [
            *super()._get_template_default_context_whitelist(),
            "is_fsm",
            "allow_material",
        ]
