# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, fields, models
from odoo.fields import Domain


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    project_id = fields.Many2one(
        'project.project', string="Project", compute='_compute_project_id', domain=[('is_template', '=', False)], store=True,
        readonly=False, copy=True, check_company=True, group_expand='_read_group_project_id',
    )

    @api.depends('template_id.project_id')
    def _compute_project_id(self):
        for slot in self:
            if slot.template_id:
                slot.previous_template_id = slot.template_id
                if slot.template_id.project_id:
                    slot.project_id = slot.template_id.project_id
            elif slot.previous_template_id and not slot.template_id and slot.previous_template_id.project_id == slot.project_id:
                slot.project_id = False
            elif self.env.context.get('default_project_id'):
                slot.project_id = self.env["project.project"].browse(self.env.context['default_project_id'])

    def _read_group_project_id(self, projects, domain):
        domain = Domain(domain)
        dom_tuples = [(cond.field_expr, cond.operator) for cond in domain.iter_conditions()]
        if self.env.context.get('planning_expand_project') and ('start_datetime', '<') in dom_tuples and ('end_datetime', '>') in dom_tuples:
            if ('project_id', '=') in dom_tuples or ('project_id', 'ilike') in dom_tuples:
                filter_domain = self._expand_domain_m2o_groupby(domain, 'project_id')
                return self.env['project.project'].search(filter_domain)
            filters = Domain.AND([[('project_id.active', '=', True)], self._expand_domain_dates(domain)])
            return self.env['planning.slot'].search(filters).mapped('project_id')
        return projects

    def _get_fields_breaking_publication(self):
        """ Fields list triggering the `publication_warning` to True when updating shifts """
        result = super()._get_fields_breaking_publication()
        result.append('project_id')
        return result

    def _display_name_fields(self):
        return super()._display_name_fields() + ['project_id']

    def _prepare_template_values(self):
        result = super()._prepare_template_values()
        return {
            'project_id': self.project_id.id,
            **result
        }

    @api.model
    def _get_template_fields(self):
        values = super()._get_template_fields()
        return {'project_id': 'project_id', **values}

    def _get_domain_template_slots(self):
        domain = Domain(super()._get_domain_template_slots())
        domain &= Domain('company_id', '=', [False, self.company_id.id])
        if self.project_id:
            domain &= Domain('project_id', '=', self.project_id.id)
        return domain

    @api.depends('role_id', 'employee_id', 'project_id', 'company_id')
    def _compute_template_autocomplete_ids(self):
        super()._compute_template_autocomplete_ids()

    @api.depends('project_id')
    def _compute_template_id(self):
        super()._compute_template_id()

    @api.depends('template_id', 'role_id', 'allocated_hours', 'project_id')
    def _compute_allow_template_creation(self):
        super()._compute_allow_template_creation()

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def write(self, vals):
        return super().write(vals)

    def _prepare_shift_vals(self):
        return {
            **super()._prepare_shift_vals(),
            'project_id': self.project_id.id,
        }

    def _get_ics_description_data(self):
        return {
            **super()._get_ics_description_data(),
            'project': self.project_id.sudo().display_name if self.project_id else '',
        }

    def _get_open_shifts_resources(self):
        # Get all resources of planned shifts having the same projects
        resources, resources_dicts = super()._get_open_shifts_resources()
        resource_ids_per_project = defaultdict(list)
        now = fields.Datetime.now()
        for project, slots in self._read_group(
            domain=[
                ('project_id', 'in', self.project_id.ids),
                ('employee_id', '!=', False),
                ('start_datetime', '!=', False),
            ],
            groupby=['project_id'],
            aggregates=['id:recordset']
        ):
            # Sort them and add them to the resources recordset and dictionaries
            slots_resources = slots.sorted(key=lambda s: abs(s.end_datetime - now)).resource_id
            resource_ids_per_project[project] = slots_resources.ids
            resources |= slots_resources
        resources_dicts.insert(0, resource_ids_per_project)
        return resources, resources_dicts

    def _get_resources_dict_values(self, resource_dict):
        self.ensure_one()
        return resource_dict.get(self.project_id, super()._get_resources_dict_values(resource_dict))

    def _print_planning_get_fields_to_copy(self):
        return super()._print_planning_get_fields_to_copy() + ['project_id']

    def _print_planning_get_slot_title(self, slot_start, slot_end, tz_info, group_by):
        res = super()._print_planning_get_slot_title(slot_start, slot_end, tz_info, group_by)

        if group_by != 'project_id' and self.project_id:
            res += ' - ' + self.project_id.name

        return res
