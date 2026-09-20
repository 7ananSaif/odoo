# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.misc import get_lang


class HrAppraisalGoal(models.Model):
    _name = 'hr.appraisal.goal'
    _inherit = ['hr.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Appraisal Goal"
    _parent_name = 'parent_id'
    _parent_store = True

    name = fields.Char(required=True)
    employee_ids = fields.Many2many(
        'hr.employee', 'hr_appraisal_goal_hr_employee_rel', 'hr_appraisal_goal_id',
        string="Employee", ondelete='cascade', tracking=True)
    employee_autocomplete_ids = fields.Many2many('hr.employee', compute='_compute_employee_autocomplete', compute_sudo=True)
    company_id = fields.Many2one('res.company', related="employee_ids.company_id", store=True)
    manager_ids = fields.Many2many(
        'hr.employee', 'hr_appraisal_goal_hr_employee_manager_rel', 'hr_appraisal_goal_id',
        string="Manager", compute="_compute_manager_ids", readonly=False, store=True, tracking=True)
    department_ids = fields.Many2many('hr.department', compute="_compute_department_ids", store=True)
    job_ids = fields.Many2many('hr.job', compute="_compute_job_ids", store=True, groups="hr.group_hr_user")
    progression = fields.Selection(selection=[
        ('000', '0%'),
        ('025', '25%'),
        ('050', '50%'),
        ('075', '75%'),
        ('100', '100%')
    ], string="Progress", default="000", tracking=True, required=True, copy=False, compute="_compute_progression",
        store=True, readonly=False, recursive=True)
    description = fields.Html()
    deadline = fields.Date(tracking=True)
    is_manager = fields.Boolean(compute='_compute_is_manager', search='_search_is_manager')
    has_edit_right = fields.Boolean(compute='_compute_has_edit_right')
    tag_ids = fields.Many2many('hr.appraisal.goal.tag', string="Tags")
    template_goal_id = fields.Many2one("hr.appraisal.goal", "Goal Template")
    number_of_sibling_goals = fields.Integer(compute='_compute_number_of_sibling_goals', store=True)
    number_of_completed_sibling_goals = fields.Integer(compute='compute_number_of_completed_sibling_goals', store=True)
    sibling_goals_ratio = fields.Float(compute="_compute_sibling_goals_ratio", store=True)
    # Goal Template
    active = fields.Boolean(default=True)
    parent_path = fields.Char(index=True)
    parent_id = fields.Many2one("hr.appraisal.goal", "Parent Goal Template", index=True, domain=[('employee_ids', '=', False)])
    child_ids = fields.One2many("hr.appraisal.goal", 'parent_id', "Sub Goal Template")
    usual_duration_month = fields.Integer(string="Usual Timing",
        help="The average timing for the goals to be completed. It will populate the estimated end date when assigned")

    @api.depends_context('uid')
    def _compute_has_edit_right(self):
        # Due to a strange framework behavior the view is not readonly when the user can't write on this model.
        for goal in self:
            goal.has_edit_right = goal.has_access('write')

    @api.depends_context('uid')
    @api.depends('employee_ids')
    def _compute_employee_autocomplete(self):
        self.employee_autocomplete_ids = self.env.user.get_employee_autocomplete_ids()

    @api.depends_context('uid')
    @api.depends('employee_ids')
    def _compute_is_manager(self):
        self.is_manager =\
            self.env.user.has_group('hr_appraisal.group_hr_appraisal_user')\
            or len(self.employee_autocomplete_ids) > 1

    def _search_is_manager(self, operator, value):
        if operator != 'in':
            return NotImplemented
        if self.env.user.has_group('hr_appraisal.group_hr_appraisal_user'):
            return Domain.TRUE
        return Domain('employee_ids', 'in', self.env.user.get_employee_autocomplete_ids().ids)

    @api.depends('employee_ids')
    def _compute_manager_ids(self):
        for goal in self:
            goal.manager_ids = goal.employee_ids.parent_id

    @api.depends('parent_id.child_ids')
    def _compute_number_of_sibling_goals(self):
        for goal in self:
            if not goal.parent_id:
                goal.number_of_sibling_goals = 0
            else:
                goal.number_of_sibling_goals = len(goal.parent_id.child_ids)

    @api.depends('parent_id.child_ids.progression')
    def compute_number_of_completed_sibling_goals(self):
        for goal in self:
            if not goal.parent_id:
                goal.number_of_completed_sibling_goals = 0
            else:
                goal.number_of_completed_sibling_goals = len(goal.parent_id.child_ids.filtered(lambda goal: goal.progression == '100'))

    @api.depends('number_of_sibling_goals', 'number_of_completed_sibling_goals')
    def _compute_sibling_goals_ratio(self):
        for goal in self:
            goal.sibling_goals_ratio = 100 * goal.number_of_completed_sibling_goals / goal.number_of_sibling_goals if goal.number_of_sibling_goals else 0

    @api.depends('child_ids.progression')
    def _compute_progression(self):
        for goal in self:
            if not goal.child_ids:
                continue
            if all(goal_child.progression == '100' for goal_child in goal.child_ids):
                goal.progression = '100'
            else:
                goal.progression = '000'

    @api.depends("employee_ids.department_id")
    def _compute_department_ids(self):
        for goal in self:
            goal.department_ids = goal.employee_ids.department_id

    @api.depends("employee_ids.job_id")
    def _compute_job_ids(self):
        for goal in self:
            goal.job_ids = goal.employee_ids.job_id

    def _notify_by_email_prepare_rendering_context(self, message, msg_vals=False, model_description=False,
                                                   force_email_company=False, force_email_lang=False,
                                                   force_record_name=False):
        render_context = super()._notify_by_email_prepare_rendering_context(
            message, msg_vals=msg_vals, model_description=model_description,
            force_email_company=force_email_company, force_email_lang=force_email_lang,
            force_record_name=force_record_name,
        )
        if self.deadline:
            render_context['subtitles'].append(
                self.env._('Deadline: %s', self.deadline.strftime(get_lang(self.env).date_format)))
        return render_context

    def action_confirm(self):
        self.write({'progression': '100'})

    ########################################## Goal template ##########################################################

    def generate_goals(self, employee_ids=[], employee_goal_dict={}):
        if not employee_ids and 'default_employee_id' in self.env.context:
            employee_ids = [self.env.context['default_employee_id']]
        if not employee_ids:
            return
        employee_goals_values = []
        for goal in self:
            for employee_id in employee_ids:
                parent_id = False
                if goal.parent_id and employee_goal_dict.get((goal.parent_id.id, employee_id), False):
                    parent_id = employee_goal_dict[goal.parent_id.id, employee_id].id
                employee_goals_values.append(goal._get_goals_values(employee_id, parent_id))

        employee_goals = self.env['hr.appraisal.goal'].sudo().create(employee_goals_values)
        if self.child_ids:
            employee_goals_by_parent_template_by_employee = employee_goals.grouped(
                lambda goal: (goal.template_goal_id.id, goal.employee_ids.id)
            )
            self.child_ids.generate_goals(employee_ids, employee_goals_by_parent_template_by_employee)

    def _get_goals_values(self, employee_id, goal_parent_id):
        self.ensure_one()
        return {
            'name': self.name,
            'description': self.description,
            'tag_ids': self.tag_ids.ids,
            'deadline': fields.Date.today() + relativedelta(months=self.usual_duration_month) if self.usual_duration_month else False,
            'employee_ids': [employee_id],
            'parent_id': goal_parent_id,
            'template_goal_id': self.id,
        }

    def action_save_as_template(self):
        if any(goal.template_goal_id for goal in self):
            raise UserError(self.env._("A goal template already exist for this goal."))
        goal_templates = self.env['hr.appraisal.goal'].create([{
            'name': goal.name,
            'description': goal.description,
            'usual_duration_month': relativedelta(goal.deadline, goal.create_date.date()).months
                if goal.deadline and goal.deadline > goal.create_date.date() else 0,
            'tag_ids': goal.tag_ids,
        } for goal in self])
        for goal_template, goal in zip(goal_templates, self):
            goal.template_goal_id = goal_template
        action = self.env['ir.actions.act_window']._for_xml_id('hr_appraisal.action_hr_appraisal_goal_template')
        if len(goal_templates.ids) == 1:
            action['view_mode'] = 'form'
            action['views'] = [(self.env.ref('hr_appraisal.hr_appraisal_goal_template_view_form').id, 'form')]
            action['res_id'] = goal_templates.id
        action['domain'] = [('id', 'in', goal_templates.ids)]
        return action

    def action_open_goal_template(self):
        self.ensure_one()
        return {
            'name': self.env._('Goals'),
            'type': 'ir.actions.act_window',
            'view_mode': 'hierarchy,form',
            'res_model': 'hr.appraisal.goal',
            'views': [
                (self.env.ref('hr_appraisal.hr_appraisal_goal_view_hierarchy').id, 'hierarchy'),
                (False, 'form'),
            ],
            'domain': [('id', '=', self.id)],
        }

    @api.model
    def action_select_employees(self):
        model = "hr.employee.public"
        list_id = "hr_appraisal.hr_employee_public_select_from_goal_view_list"
        if self.env['hr.employee'].has_access('read'):
            model = "hr.employee"
            list_id = "hr_appraisal.hr_employee_select_from_goal_view_list"
        return {
            'name': self.env._("Select Employees"),
            'type': 'ir.actions.act_window',
            'res_model': model,
            'views': [
                [self.env.ref(list_id).id, 'list'],
            ],
            'domain': [('id', 'in', self.env.user.get_employee_autocomplete_ids().ids)],
            'target': 'new',
            'context': {'goals_ids': self.env.context.get('goals_ids')}
        }

    ######################################### ORM method ##############################################################

    def action_archive(self):
        super().action_archive()
        if self.child_ids:
            self.child_ids.action_archive()

    def copy_data(self, default=None):
        vals_list = super().copy_data(default)
        for goal, vals in zip(self, vals_list):
            vals['name'] = self.env._('%s (copy)', goal.name)
            if goal.deadline and goal.deadline < fields.Date.today():
                vals['deadline'] = False
        return vals_list

    def copy(self, default=None):
        if not self.child_ids:
            return super().copy(default)
        list_of_goals_domain = [
            Domain.AND([
                Domain('id', 'child_of', goal.id),
                Domain('id', '!=', goal.id)
            ]) for goal in self
        ]
        if len(list_of_goals_domain) == 1:
            domain = list_of_goals_domain
        else:
            domain = Domain.OR(list_of_goals_domain)

        all_goal_children_ids = self.env['hr.appraisal.goal'].search(domain).ids
        if any(goal.id in all_goal_children_ids for goal in self):
            raise UserError(self.env._('You cannot duplicate at the same time a goal and one of its children.\n'
            'Duplicating a goal will also duplicate its children.'))

        new_goal_templates = super().copy(default)
        # Build the hierarchy of new goals
        res = self.child_ids.copy(default).grouped('parent_id')
        for old_goal_template, new_goal_template in zip(self, new_goal_templates):
            if res.get(old_goal_template):
                res[old_goal_template].parent_id = new_goal_template.id
        return new_goal_templates

    def recursive_unlink(self):
        if self.child_ids:
            self.child_ids.recursive_unlink()
        self.exists().unlink()
