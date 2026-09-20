# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ["project.task", "timer.parent.mixin", "timesheet.grid.mixin"]

    timer_start = fields.Datetime(groups='hr_timesheet.group_hr_timesheet_user')
    timer_pause = fields.Datetime(groups='hr_timesheet.group_hr_timesheet_user')
    is_timer_running = fields.Boolean(groups='hr_timesheet.group_hr_timesheet_user')
    user_timer_id = fields.One2many(groups='hr_timesheet.group_hr_timesheet_user')
    timesheet_unit_amount = fields.Float(compute='_compute_timesheet_unit_amount', groups='hr_timesheet.group_hr_timesheet_user')
    display_timesheet_timer = fields.Boolean("Display Timesheet Time", compute='_compute_display_timesheet_timer', export_string_translation=False, groups='hr_timesheet.group_hr_timesheet_user')

    @api.depends('user_timer_id')
    def _compute_timesheet_unit_amount(self):
        if not any(self._ids):
            for task in self:
                unit_amount = 0.0
                if task.user_timer_id:
                    unit_amount = task.filtered(lambda t: (t.id or t.origin.id) == task.user_timer_id.id).unit_amount or 0.0
                task.timesheet_unit_amount = unit_amount
            return
        timesheet_read = self.env['account.analytic.line'].search_read(
            [('id', 'in', self.user_timer_id.mapped('res_id'))],
            ['unit_amount'],
        )
        unit_amount_per_timesheet_id = {res['id']: res['unit_amount'] for res in timesheet_read}
        for task in self:
            timesheet_id = task.user_timer_id.res_id
            if timesheet_id:
                task.timesheet_unit_amount = unit_amount_per_timesheet_id.get(timesheet_id, 0.0)
            else:
                task.timesheet_unit_amount = 0.0

    @api.depends('allow_timesheets', 'analytic_account_active')
    def _compute_display_timesheet_timer(self):
        user_has_employee_or_only_one = None
        for task in self:
            display_timesheet_timer = task.allow_timesheets and task.analytic_account_active and not task.encode_uom_in_days
            if display_timesheet_timer:
                if user_has_employee_or_only_one is None:
                    user_has_employee_or_only_one = bool(self.env.user.employee_id) \
                        or self.env['hr.employee'].sudo().search_count([('user_id', '=', self.env.uid)]) == 1
                display_timesheet_timer = user_has_employee_or_only_one
            task.display_timesheet_timer = display_timesheet_timer

    def _compute_allocated_hours(self):
        # Only change values when creating a new record from the gantt view
        # or the existing tasks that doesn't allow timesheets
        timsheeted_tasks = self.filtered(lambda task: task._origin and task.allow_timesheets)
        super(ProjectTask, self - timsheeted_tasks)._compute_allocated_hours()

    @api.onchange('project_id')
    def _onchange_project_id(self):
        # If task has non-validated timesheets AND new project has not the timesheets feature enabled, raise a warning notification
        if not all(t.validated for t in self.timesheet_ids) and not self.project_id.allow_timesheets:
            return {
                'warning': {
                    'title': _("Warning"),
                    'message': _("Moving this task to a project without timesheet support will retain timesheet drafts in the original project. "
                                 "Although they won't be visible here, you can still edit them using the Timesheets app."),
                    'type': "notification",
                },
            }

    def write(self, vals):
        res = super().write(vals)
        if vals.get('project_id') and not self.project_id.sudo().allow_timesheets:
            timers = self.env['timer.timer'].sudo().search([
                ('parent_res_model', '=', 'project.task'),
                ('parent_res_id', 'in', self.ids),
                ('res_model', '=', 'account.analytic.line'),
            ])
            if timers:
                timesheets = self.env['account.analytic.line'].browse(timers.mapped('res_id')).sudo()
                timers.unlink()
                if timesheets_to_remove := timesheets.filtered(lambda t: t.unit_amount == 0):
                    timesheets_to_remove.unlink()
        return res

    def _set_allocated_hours_for_tasks(self):
        super(ProjectTask, self.filtered(lambda task: not task.allow_timesheets))._set_allocated_hours_for_tasks()

    def _gantt_progress_bar_project_id(self, res_ids):
        timesheet_read_group = self.env['account.analytic.line'].sudo()._read_group(
            [('project_id', 'in', res_ids)],
            ['project_id'],
            ['unit_amount:sum'],
        )
        return {
            project.id: {
                'value': unit_amount_sum,
                'max_value': project.sudo().allocated_hours,
            }
            for project, unit_amount_sum in timesheet_read_group
        }

    def _gantt_progress_bar(self, field, res_ids, start, stop):
        if field == 'project_id':
            return dict(
                self._gantt_progress_bar_project_id(res_ids),
                warning=_("This project isn't expected to have task during this period."),
            )
        return super()._gantt_progress_bar(field, res_ids, start, stop)

    def action_view_subtask_timesheet(self):
        action = super().action_view_subtask_timesheet()
        grid_view_id = self.env.ref('timesheet_grid.timesheet_view_grid_by_employee').id
        action['views'] = [
            [grid_view_id, view_mode] if view_mode == 'grid' else [view_id, view_mode]
            for view_id, view_mode in action['views']
        ]
        return action

    def action_timer_start(self):
        if self.display_timesheet_timer:
            super().action_timer_start()

    def action_timer_stop(self):
        # timer was either running or paused
        if self.display_timesheet_timer and self.user_timer_id:
            timesheet = self._get_record_with_timer_running()
            if timesheet:
                return {
                    "name": _("Confirm Time Spent"),
                    "type": "ir.actions.act_window",
                    "res_model": 'hr.timesheet.stop.timer.confirmation.wizard',
                    'context': {
                        'default_timesheet_id': timesheet.id,
                        'dialog_size': 'medium',
                    },
                    "views": [[self.env.ref('timesheet_grid.hr_timesheet_stop_timer_confirmation_wizard_view_form').id, "form"]],
                    "target": 'new',
                }
            else:
                return super().action_timer_stop()
        return False

    def get_allocated_hours_field(self):
        return 'allocated_hours'

    def get_worked_hours_fields(self):
        return ['effective_hours', 'subtask_effective_hours']

    def _get_hours_to_plan(self):
        return self.remaining_hours

    def _create_record_to_start_timer(self):
        """ Create a timesheet to launch a timer """
        return self.env['account.analytic.line'].create({
            'task_id': self.id,
            'project_id': self.project_id.id,
            'date': fields.Date.context_today(self),
            'name': '/',
            'user_id': self.env.uid,
        })

    def _action_interrupt_user_timers(self):
        """ Call action interrupt user timers to launch a new one
            Stop the existing runnning timer before launching a new one.
        """
        self.action_timer_stop()
