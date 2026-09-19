# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from markupsafe import Markup
import pytz

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.fields import Command, Domain
from odoo.tools import get_lang
from odoo.tools.intervals import Intervals
from odoo.tools.date_utils import sum_intervals
from odoo.addons.timer.utils.timer_utils import round_time_spent


class ProjectTask(models.Model):
    _inherit = "project.task"

    @api.model
    def default_get(self, fields):
        context = dict(self.env.context)
        is_fsm_mode = self.env.context.get('fsm_mode')
        fsm_project = False
        if is_fsm_mode and 'project_id' in fields and not self.env.context.get('default_parent_id'):
            company_id = self.env.context.get('default_company_id') or self.env.company.id
            fsm_project = self.env['project.project'].search([('is_fsm', '=', True), ('company_id', '=', company_id)], order='sequence, name, id', limit=1)
            if fsm_project:
                context['default_project_id'] = self.env.context.get('default_project_id', fsm_project.id)
        result = super(ProjectTask, self.with_context(context)).default_get(fields)
        if fsm_project:
            result.update({
                'company_id': company_id,
                'stage_id': self.stage_find(fsm_project.id, [('fold', '=', False)])
            })
        return result

    is_fsm = fields.Boolean(related='project_id.is_fsm')
    fsm_done = fields.Boolean("Task Done", compute='_compute_fsm_done', readonly=False, store=True, copy=False)
    # Use to count conditions between : time, worksheet and materials
    # If 2 over 3 are enabled for the project, the required count = 2
    # If 1 over 3 is met (enabled + encoded), the satisfied count = 2
    display_enabled_conditions_count = fields.Integer(compute='_compute_display_conditions_count', export_string_translation=False)
    display_satisfied_conditions_count = fields.Integer(compute='_compute_display_conditions_count', export_string_translation=False)
    display_mark_as_done_primary = fields.Boolean(compute='_compute_mark_as_done_buttons', export_string_translation=False)
    display_mark_as_done_secondary = fields.Boolean(compute='_compute_mark_as_done_buttons', export_string_translation=False)
    partner_city = fields.Char(related='partner_id.city', readonly=False)
    partner_zip = fields.Char(string='ZIP', related='partner_id.zip')
    partner_street = fields.Char(related='partner_id.street')
    partner_street2 = fields.Char(related='partner_id.street2')
    partner_country_id = fields.Many2one('res.country', related='partner_id.country_id')
    partner_state_id = fields.Many2one('res.country.state', string='Customer State', related='partner_id.state_id')
    is_task_phone_update = fields.Boolean(compute='_compute_is_task_phone_update', export_string_translation=False)

    # FSM Report fields
    display_sign_report_primary = fields.Boolean(compute='_compute_display_sign_report_buttons', export_string_translation=False)
    display_sign_report_secondary = fields.Boolean(compute='_compute_display_sign_report_buttons', export_string_translation=False)
    display_send_report_primary = fields.Boolean(compute='_compute_display_send_report_buttons', export_string_translation=False)
    display_send_report_secondary = fields.Boolean(compute='_compute_display_send_report_buttons', export_string_translation=False)
    fsm_is_sent = fields.Boolean(readonly=True, copy=False, export_string_translation=False)
    show_customer_preview = fields.Boolean(compute='_compute_show_customer_preview', export_string_translation=False)
    worksheet_signature = fields.Binary('Signature', copy=False, attachment=True)
    worksheet_signed_by = fields.Char('Signed By', copy=False)
    allow_geolocation = fields.Boolean(related="project_id.allow_geolocation")

    @api.depends('planned_date_begin', 'date_deadline', 'user_ids')
    def _compute_planning_overlap(self):
        """Computes overlap warnings for fsm tasks.

            Unlike other tasks, fsm tasks overlap in two scenarios:
            1. When the combined allocated hours of an fsm task and a normal task exceed the user's workable hours.
            2. When two fsm tasks have overlapping planned dates.

            Example:
            - ProjectTask A (normal) conflicts with ProjectTask B (fsm) if their combined hours > user's workable hours. Both have 1 conflict.
            - Introduce ProjectTask C (fsm) with no allocated hours (no conflict with ProjectTask A) but same time period as ProjectTask B.
            Result: ProjectTask A has 1 conflict, ProjectTask B has 2 conflicts, ProjectTask C has 1 conflict.
        """
        fsm_tasks = self.filtered("is_fsm")
        overlap_mapping = super()._compute_planning_overlap()
        for row in self._fetch_planning_overlap([('is_fsm', '=', True)]):
            task_id = row["id"]
            if task_id not in overlap_mapping:
                overlap_mapping[task_id] = {row["user_id"]: {}}
            if row["user_id"] not in overlap_mapping[task_id]:
                overlap_mapping[task_id][row["user_id"]] = {}
            overlap_data = overlap_mapping[task_id][row["user_id"]]
            overlap_data['partner_name'] = row['partner_name']
            existing_task_ids = overlap_data.get('overlapping_tasks_ids', [])
            overlap_data['overlapping_tasks_ids'] = list(set(existing_task_ids) | set(row['task_ids']))
            existing_min_date = overlap_data.get('min_planned_date_begin', row['min'])
            overlap_data['min_planned_date_begin'] = min(existing_min_date, row['min'])
            existing_max_date = overlap_data.get('max_date_deadline', row['max'])
            overlap_data['max_date_deadline'] = max(existing_max_date, row['max'])
        if not overlap_mapping:
            fsm_tasks.planning_overlap = False
            return
        for task in fsm_tasks:
            overlap_messages = []
            for task_mapping in overlap_mapping.get(task.id, {}).values():
                message = _('%(partner)s has %(number)s tasks at the same time.', partner=task_mapping['partner_name'], number=len(task_mapping['overlapping_tasks_ids']))
                overlap_messages.append(message)
            task.planning_overlap = ' '.join(overlap_messages) or False

    @property
    def TASK_PORTAL_READABLE_FIELDS(self):
        return super().TASK_PORTAL_READABLE_FIELDS | {'is_fsm',
                                              'planned_date_begin',
                                              'fsm_done',
                                              'partner_phone',
                                              'partner_city',}

    @api.depends(
        'fsm_done', 'is_fsm', 'timer_start',
        'display_enabled_conditions_count', 'display_satisfied_conditions_count')
    def _compute_mark_as_done_buttons(self):
        for task in self:
            primary, secondary = True, True
            if task.fsm_done or not task.is_fsm or task.sudo().timer_start:
                primary, secondary = False, False
            else:
                if task.display_enabled_conditions_count == task.display_satisfied_conditions_count:
                    secondary = False
                else:
                    primary = False
            task.update({
                'display_mark_as_done_primary': primary,
                'display_mark_as_done_secondary': secondary,
            })

    @api.depends('partner_phone', 'partner_id.phone')
    def _compute_is_task_phone_update(self):
        for task in self:
            task.is_task_phone_update = task.partner_phone != task.partner_id.phone

    @api.depends('project_id.allow_timesheets', 'total_hours_spent')
    def _compute_display_conditions_count(self):
        for task in self:
            enabled = 1 if task.project_id.allow_timesheets else 0
            satisfied = 1 if enabled and task.total_hours_spent else 0
            task.update({
                'display_enabled_conditions_count': enabled,
                'display_satisfied_conditions_count': satisfied
            })

    @api.depends('fsm_done')
    def _compute_display_timesheet_timer(self):
        fsm_done_tasks = self.filtered('fsm_done')
        fsm_done_tasks.display_timesheet_timer = False
        super(ProjectTask, self - fsm_done_tasks)._compute_display_timesheet_timer()

    @api.onchange('date_deadline', 'planned_date_begin')
    def _onchange_planned_dates(self):
        if not self.is_fsm:
            return super()._onchange_planned_dates()

    def write(self, vals):
        self_fsm = self.filtered('is_fsm')
        basic_projects = self - self_fsm
        if basic_projects:
            res = super(ProjectTask, basic_projects).write(vals.copy())
            if not self_fsm:
                return res

        is_start_date_set = bool(vals.get('planned_date_begin', False))
        is_end_date_set = bool(vals.get("date_deadline", False))
        both_dates_changed = 'planned_date_begin' in vals and 'date_deadline' in vals
        self_fsm = self_fsm.with_context(fsm_mode=True)

        if self_fsm and (
            (both_dates_changed and is_start_date_set != is_end_date_set) or (not both_dates_changed and (
                ('planned_date_begin' in vals and not all(bool(t.date_deadline) == is_start_date_set for t in self)) or \
                ('date_deadline' in vals and not all(bool(t.planned_date_begin) == is_end_date_set for t in self))
            ))
        ):
            vals.update({"date_deadline": False, "planned_date_begin": False})

        return super(ProjectTask, self_fsm).write(vals)

    @api.model
    def _group_expand_project_ids(self, projects, domain):
        res = super()._group_expand_project_ids(projects, domain)
        if self.env.context.get('fsm_mode'):
            search_on_comodel = self._search_on_comodel(domain, "project_id", "project.project", [('is_fsm', '=', True)])
            res &= search_on_comodel
        return res

    def _group_expand_user_ids_domain(self, domain_expand):
        if self.env.context.get('fsm_mode'):
            new_domain_expand = Domain.OR([[
                ('is_closed', '=', False),
                ('planned_date_begin', '=', False),
                ('date_deadline', '=', False),
            ], domain_expand])
            return new_domain_expand & Domain('is_fsm', '=', True)
        else:
            return super()._group_expand_user_ids_domain(domain_expand)

    def _compute_fsm_done(self):
        closed_tasks = self.filtered(lambda t: t.is_closed)
        closed_tasks.fsm_done = True

    def action_timer_start(self):
        if not self.user_timer_id.timer_start and self.display_timesheet_timer:
            super().action_timer_start()
            if not self.is_fsm:
                return

            if self.allow_geolocation and (geolocation := self.env.context.get("geolocation")):
                success = geolocation.get("success")
                latitude = 0
                longitude = 0
                localisation_start = False

                if success:
                    latitude = geolocation["latitude"]
                    longitude = geolocation["longitude"]
                    localisation_start = self.env["base.geocoder"]._get_localisation(latitude=latitude, longitude=longitude)

                    geolocation_message = _("GPS Coordinates: %(localisation_start)s (%(latitude)s, %(longitude)s)",
                        localisation_start=localisation_start,
                        latitude=latitude,
                        longitude=longitude,
                    )
                else:
                    geolocation_message = geolocation.get("message", _("Location error"))
            else:
                geolocation_message = False

            time = fields.Datetime.context_timestamp(self, self.timer_start)
            body = _(
                'Timer started at: %(date)s %(time)s',
                date=time.strftime(get_lang(self.env).date_format),
                time=time.strftime(get_lang(self.env).time_format),
            )
            if geolocation_message:
                body += Markup("<br/>") + geolocation_message
                if latitude and latitude:
                    body += Markup(" <a href='https://maps.google.com?q={latitude},{longitude}' target='_blank'>{label}</a>").format(
                        latitude=latitude,
                        longitude=longitude,
                        label=_("View on Map")
                    )
            self.message_post(body=body)

    def action_view_timesheets(self):
        kanban_view = self.env.ref('hr_timesheet.view_kanban_account_analytic_line')
        form_view = self.env.ref('industry_fsm.timesheet_view_form')
        list_view = self.env.ref('industry_fsm.timesheet_view_tree_user_inherit')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Time'),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form,kanban',
            'views': [(list_view.id, 'list'), (kanban_view.id, 'kanban'), (form_view.id, 'form')],
            'domain': [('task_id', '=', self.id), ('project_id', '!=', False)],
            'context': {
                'fsm_mode': True,
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
            }
        }

    def _get_action_fsm_task_mobile_view(self):
        action = self.env['ir.actions.act_window']._for_xml_id('industry_fsm.project_task_action_fsm')
        mobile_form_view = self.env.ref('industry_fsm.project_task_view_mobile_form', raise_if_not_found=False)
        if mobile_form_view:
            action['views'] = [(mobile_form_view.id, 'form')]
        context = action.get('context', {})
        context = context.replace('uid', str(self.env.uid))
        context = dict(literal_eval(context), active_test=True)
        fsm_project_count = self.env['project.project'].search_count([('is_fsm', '=', True)], limit=2)
        context.update(
            industry_fsm_one_project=fsm_project_count == 1,
            industry_fsm_hide_user_ids=bool(self.user_ids) and self.env.user not in self.user_ids,
        )
        action['context'] = context
        action['view_mode'] = 'form'
        action['res_id'] = self.id
        return action

    def action_fsm_validate(self, stop_running_timers=False):
        """ Moves Task to done state.
            If allow billable on task, timesheet product set on project and user has privileges :
            Create SO confirmed with time and material.
        """
        Timer = self.env['timer.timer']
        running_timers = Timer.search([('parent_res_model', '=', 'project.task'), ('parent_res_id', 'in', self.ids)])
        if running_timers:
            if stop_running_timers:
                self._stop_all_timers_and_update_timesheets(running_timers)
            else:
                wizard = self.env['project.task.stop.timers.wizard'].create({
                    'line_ids': [Command.create({'task_id': task.id}) for task in self],
                })
                return {
                    'name': _('Do you want to stop the running timers?'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'view_id': self.env.ref('industry_fsm.view_task_stop_timer_wizard_form').id,
                    'target': 'new',
                    'res_model': 'project.task.stop.timers.wizard',
                    'res_id': wizard.id,
                }

        self.write({'fsm_done': True, 'state': '1_done'})

        return True

    @api.model
    def _stop_all_timers_and_update_timesheets(self, running_timers):
        ConfigParameter = self.env['ir.config_parameter'].sudo()
        Timesheet = self.env['account.analytic.line']

        if not running_timers:
            return Timesheet
        if any(
            timer.res_model != 'account.analytic.line'
            or (timer.parent_res_model and timer.parent_res_model != 'project.task')
            for timer in running_timers
        ):
            raise UserError(_('All running timers should be linked to a timesheet and a task.'))

        result = Timesheet
        minimum_duration = int(ConfigParameter.get_param('timesheet_grid.timesheet_min_duration', 0))
        rounding = int(ConfigParameter.get_param('timesheet_grid.timesheet_rounding', 0))
        if running_timers:
            timesheets = self.env['account.analytic.line'].sudo().search([('id', 'in', running_timers.mapped('res_id'))])
            timesheets_dict = {timesheet.id: timesheet for timesheet in timesheets}
            for timer in running_timers:
                timesheet = timesheets_dict[timer.res_id]
                minutes_spent = timer._get_minutes_spent()
                timesheet.write({'unit_amount': round_time_spent(minutes_spent, minimum_duration, rounding) / 60})
                result += timesheet
            running_timers.sudo().unlink()

        return result

    def action_fsm_navigate(self):
        if not self.partner_id.city or not self.partner_id.country_id:
            return {
                'name': _('Customer'),
                'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'res_id': self.partner_id.id,
                'view_mode': 'form',
                'view_id': self.env.ref('industry_fsm.view_partner_address_form_industry_fsm').id,
                'target': 'new',
            }
        return self.partner_id.action_partner_navigate()

    def web_read(self, specification: dict[str, dict]) -> list[dict]:
        if len(self) == 1 and 'partner_id' in specification and 'show_address_if_fsm' in specification['partner_id'].get('context', {}):
            specification['partner_id']['context']['show_address'] = self.is_fsm
        return super().web_read(specification)

    def _server_action_project_task_fsm(self, xml_id_multiple_fsm_projects, xml_id_one_fsm_project, default_user_ids=False):
        project_ids = self.env['project.project'].search([('is_fsm', '=', True)], limit=2)
        if len(project_ids) <= 1:
            action_id = xml_id_one_fsm_project
            project_id = project_ids.id
        else:
            action_id = xml_id_multiple_fsm_projects
            project_id = False
        action = self.env['ir.actions.act_window']._for_xml_id(action_id)
        context = literal_eval(action.get('context', '{}'))
        allow_timesheets = any(project.allow_timesheets for project in project_ids)
        if project_id:
            context['default_project_id'] = project_id
        return {
            **action,
            'context': {
                **context,
                'default_user_ids': default_user_ids,
                'allow_timesheets': allow_timesheets,
            },
            'domain': Domain.AND([
                literal_eval(action.get('domain', [])),
                [('has_template_ancestor', '=', False)]
            ]),
        }

    # ---------------------------------------------------------
    # FSM Report
    # ---------------------------------------------------------

    def _compute_display_send_report_buttons(self):
        self.display_send_report_primary = False
        self.display_send_report_secondary = False

    def _compute_display_sign_report_buttons(self):
        self.display_sign_report_primary = False
        self.display_sign_report_secondary = False

    def _compute_show_customer_preview(self):
        for task in self:
            task.show_customer_preview = task.fsm_is_sent or task.worksheet_signature

    def _has_to_be_signed(self):
        self.ensure_one()
        return self._is_fsm_report_available() and not self.worksheet_signature

    def _is_fsm_report_available(self):
        self.ensure_one()
        return self.timesheet_ids

    def _get_send_report_action(self):
        template_id = self.env.ref('industry_fsm.mail_template_data_task_report').id
        self.message_subscribe(partner_ids=self.partner_id.ids)
        return {
            'name': _("Send Field Service Report"),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_composition_mode': 'mass_mail' if len(self.ids) > 1 else 'comment',
                'default_model': 'project.task',
                'default_res_ids': self.ids,
                'default_template_id': template_id,
                'fsm_mark_as_sent': True,
            },
        }

    def action_send_report(self):
        tasks_with_report = self.filtered(lambda task: task._is_fsm_report_available())
        if not tasks_with_report:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _("There are no reports to send."),
                    'sticky': False,
                    'type': 'danger',
                },
            }
        action = tasks_with_report._get_send_report_action()
        if not self.env.context.get('discard_logo_check') and self.env.is_admin() and not self.env.company.external_report_layout_id:
            layout_action = self.env['ir.actions.report']._action_configure_external_report_layout(action)
            action.pop('close_on_report_download', None)
            return layout_action
        return action

    def action_preview_worksheet(self):
        self.ensure_one()
        source = 'fsm' if self.env.context.get('fsm_mode', False) else 'project'
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': self.get_portal_url(query_string=f'&source={source}')
        }

    def _message_post_after_hook(self, message, msg_vals):
        if self.env.context.get('fsm_mark_as_sent') and not self.fsm_is_sent:
            self.fsm_is_sent = True
        return super()._message_post_after_hook(message, msg_vals)

    # ---------------------------------------------------------
    # Business Methods
    # ---------------------------------------------------------

    def _get_projects_to_make_billable_domain(self, additional_domain=None):
        return Domain.AND([
            super()._get_projects_to_make_billable_domain(additional_domain),
            [('is_fsm', '=', False)],
        ])

    def _allocated_hours_per_user_for_scale(self, users, start, stop):
        fsm_tasks = self.filtered("is_fsm")
        allocated_hours_mapped = super(ProjectTask, self - fsm_tasks)._allocated_hours_per_user_for_scale(users, start, stop)
        users_work_intervals, dummy = users.sudo()._get_valid_work_intervals(start, stop)
        for task in fsm_tasks:
            # if the task goes over the gantt period, compute the duration only within
            # the gantt period
            max_start = max(start, pytz.utc.localize(task.planned_date_begin))
            min_end = min(stop, pytz.utc.localize(task.date_deadline))
            # for forecast tasks, use the conjunction between work intervals and task.
            interval = Intervals([(
                max_start, min_end, self.env['resource.calendar.attendance']
            )])
            duration = (task.date_deadline - task.planned_date_begin).total_seconds() / 3600.0 if task.planned_date_begin and task.date_deadline else 0.0
            nb_hours_per_user = (sum_intervals(interval) / (len(task.user_ids) or 1)) if duration < 24 else 0.0
            for user in task.user_ids:
                if duration < 24:
                    allocated_hours_mapped[user.id] += nb_hours_per_user
                else:
                    work_intervals = interval & users_work_intervals[user.id]
                    allocated_hours_mapped[user.id] += sum_intervals(work_intervals)
        return allocated_hours_mapped

    def action_fsm_view_overlapping_tasks(self):
        action = super().action_fsm_view_overlapping_tasks()
        if self.is_fsm:
            action['context']['fsm_mode'] = True
            action['domain'] = Domain.AND([
                action['domain'],
                [('is_fsm', '=', True)],
            ])
        return action

    def _prepare_domains_for_all_deadlines(self, date_start, date_end):
        domain = super()._prepare_domains_for_all_deadlines(date_start, date_end)
        if self.env.context.get('fsm_mode'):
            domain['project'] = Domain.AND([
                domain['project'],
                [('is_fsm', '=', True)]
            ])
            domain['milestone'] = Domain.AND([
                domain['milestone'],
                [('project_id.is_fsm', '=', True)]
            ])
        return domain

    def _get_report_base_filename(self):
        self.ensure_one()
        return 'Field Service Report %s - %s' % (self.name, self.partner_id.name)
