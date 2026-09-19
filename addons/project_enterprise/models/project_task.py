# Part of Odoo. See LICENSE file for full copyright and licensing details.

from pytz import utc, timezone
from collections import defaultdict
from datetime import timedelta, datetime, time
from dateutil.relativedelta import relativedelta
import pytz

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.exceptions import UserError
from odoo.tools import _, format_list, topological_sort, get_lang, babel_locale_parse
from odoo.tools.intervals import Intervals
from odoo.tools.date_utils import sum_intervals, get_timedelta, weeknumber, weekstart, weekend
from odoo.tools.sql import SQL
from odoo.addons.resource.models.utils import filter_domain_leaf

PROJECT_TASK_WRITABLE_FIELDS = {
    'planned_date_begin',
}


class ProjectTask(models.Model):
    _inherit = "project.task"

    planned_date_begin = fields.Datetime("Start date", tracking=True, copy=False)
    # planned_date_start is added to be able to display tasks in calendar view because both start and end date are mandatory
    planned_date_start = fields.Datetime(compute="_compute_planned_date_start", inverse='_inverse_planned_date_start', search="_search_planned_date_start")
    allocated_hours = fields.Float(compute='_compute_allocated_hours', store=True, readonly=False)
    # Task Dependencies fields
    display_warning_dependency_in_gantt = fields.Boolean(compute="_compute_display_warning_dependency_in_gantt", export_string_translation=False)
    planning_overlap = fields.Html(compute='_compute_planning_overlap', search='_search_planning_overlap', export_string_translation=False)
    dependency_warning = fields.Html(compute='_compute_dependency_warning', search='_search_dependency_warning', export_string_translation=False)

    # User names in popovers
    user_names = fields.Char(compute='_compute_user_names', export_string_translation=False)
    user_ids = fields.Many2many(group_expand="_group_expand_user_ids")
    partner_id = fields.Many2one(group_expand="_group_expand_partner_ids")
    project_id = fields.Many2one(group_expand="_group_expand_project_ids")

    _planned_dates_check = models.Constraint(
        'CHECK ((planned_date_begin <= date_deadline))',
        "The planned start date must be before the planned end date.",
    )

    # action_gantt_reschedule utils
    _WEB_GANTT_RESCHEDULE_WORK_INTERVALS_CACHE_KEY = 'work_intervals'
    _WEB_GANTT_RESCHEDULE_RESOURCE_VALIDITY_CACHE_KEY = 'resource_validity'

    @property
    def TASK_PORTAL_WRITABLE_FIELDS(self):
        return super().TASK_PORTAL_WRITABLE_FIELDS | PROJECT_TASK_WRITABLE_FIELDS

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)
        if self.env.context.get('scale', False) not in ("month", "year"):
            return result

        planned_date_begin = result.get('planned_date_begin', self.env.context.get('planned_date_begin', False))
        date_deadline = result.get('date_deadline', self.env.context.get('date_deadline', False))
        if planned_date_begin and date_deadline:
            user_ids = self.env.context.get('user_ids', [])
            planned_date_begin, date_deadline = self._calculate_planned_dates(planned_date_begin, date_deadline, user_ids)
            result.update(planned_date_begin=planned_date_begin, date_deadline=date_deadline)
        return result

    def action_unschedule_task(self):
        self.write({
            'planned_date_begin': False,
            'date_deadline': False
        })

    @api.depends('is_closed')
    def _compute_display_warning_dependency_in_gantt(self):
        for task in self:
            task.display_warning_dependency_in_gantt = not task.is_closed

    @api.onchange('date_deadline', 'planned_date_begin')
    def _onchange_planned_dates(self):
        if not self.date_deadline:
            self.planned_date_begin = False

    @api.depends('date_deadline', 'planned_date_begin', 'user_ids')
    def _compute_allocated_hours(self):
        for task in self:
            if not task.date_deadline or not task.planned_date_begin:
                task.allocated_hours = 0
                continue
            date_begin, date_end = task._calculate_planned_dates(
                task.planned_date_begin,
                task.date_deadline,
                user_id=task.user_ids.ids if len(task.user_ids) == 1 else None,
                calendar=task.env.company.resource_calendar_id if len(task.user_ids) != 1 else None,
            )
            if len(task.user_ids) == 1:
                tz = task.user_ids.tz or 'UTC'
                # We need to browse on res.users in order to bypass the new origin id
                work_intervals, _dummy = task.user_ids.sudo()._get_valid_work_intervals(
                    date_begin.astimezone(timezone(tz)),
                    date_end.astimezone(timezone(tz))
                )
                work_duration = sum_intervals(work_intervals[task.user_ids._ids[0]])
            else:
                tz = task.env.company.resource_calendar_id.tz or 'UTC'
                work_duration = task.env.company.resource_calendar_id.get_work_hours_count(
                    date_begin.astimezone(timezone(tz)),
                    date_end.astimezone(timezone(tz)),
                    compute_leaves=False
                )
            task.allocated_hours = round(work_duration, 2)

    def _fetch_planning_overlap(self, additional_domain=None):
        domain = Domain([
            ('active', '=', True),
            ('is_closed', '=', False),
            ('planned_date_begin', '!=', False),
            ('date_deadline', '!=', False),
            ('date_deadline', '>', fields.Datetime.now()),
            ('project_id', '!=', False),
        ])
        if additional_domain:
            domain &= Domain(additional_domain)
        domain = domain.optimize_full(self)

        task1 = self._table
        query = self._search(domain & Domain('id', 'in', self.ids), bypass_access=True)

        # join for overlapping tasks (task2)
        task2 = query.make_alias(task1, 'T2')
        query.add_join('JOIN', task2, self._table_sql, SQL(
            "%s != %s AND (%s::TIMESTAMP, %s::TIMESTAMP) OVERLAPS (%s::TIMESTAMP, %s::TIMESTAMP)",
            SQL.identifier(task1, 'id'),
            SQL.identifier(task2, 'id'),
            SQL.identifier(task1, 'planned_date_begin'),
            SQL.identifier(task1, 'date_deadline'),
            SQL.identifier(task2, 'planned_date_begin'),
            SQL.identifier(task2, 'date_deadline'),
        ))
        query.add_where(domain._to_sql(self, task2, query))

        # overlapping tasks must be for the same user
        task1_user_rel = query.join(task1, 'id', 'project_task_user_rel', 'task_id', 'TU1')
        task2_user_rel = query.join(task2, 'id', 'project_task_user_rel', 'task_id', 'TU2')
        query.add_where(SQL(
            "%s = %s",
            SQL.identifier(task1_user_rel, 'user_id'),
            SQL.identifier(task2_user_rel, 'user_id'),
        ))

        # group by task, user, partner name, and order by partner name
        task1_user = query.join(task1_user_rel, 'user_id', 'res_users', 'id', 'U')
        task1_partner = query.join(task1_user, 'partner_id', 'res_partner', 'id', 'P')
        task1_partner_name = self.env['res.partner']._field_to_sql(task1_partner, 'name', query)
        query.groupby = SQL(", ").join([
            SQL.identifier(task1, 'id'),
            SQL.identifier(task1_user, 'id'),
            task1_partner_name,
        ])
        query.order = task1_partner_name

        sql = query.select(
            SQL.identifier(task1, 'id'),
            SQL.identifier(task1, 'planned_date_begin'),
            SQL.identifier(task1, 'date_deadline'),
            SQL("ARRAY_AGG(%s) AS task_ids", SQL.identifier(task2, 'id')),
            SQL("MIN(%s)", SQL.identifier(task2, 'planned_date_begin')),
            SQL("MAX(%s)", SQL.identifier(task2, 'date_deadline')),
            SQL("%s AS user_id", SQL.identifier(task1_user, 'id')),
            SQL("%s AS partner_name", task1_partner_name),
            SQL("%s", self._field_to_sql(task1, 'allocated_hours', query)),
            SQL("SUM(%s)", self._field_to_sql(task2, 'allocated_hours', query)),
        )
        return self.env.execute_query_dict(sql)

    def _get_planning_overlap_per_task(self):
        if not self.ids:
            return {}
        self.flush_model(['active', 'planned_date_begin', 'date_deadline', 'user_ids', 'project_id', 'is_closed'])

        res = defaultdict(lambda: defaultdict(lambda: {
            'overlapping_tasks_ids': [],
            'sum_allocated_hours': 0,
            'min_planned_date_begin': False,
            'max_date_deadline': False,
        }))
        for row in self._fetch_planning_overlap([('allocated_hours', '>', 0)]):
            res[row['id']][row['user_id']] = {
                'partner_name': row['partner_name'],
                'overlapping_tasks_ids': row['task_ids'],
                'sum_allocated_hours': row['sum'] + row['allocated_hours'],
                'min_planned_date_begin': min(row['min'], row['planned_date_begin']),
                'max_date_deadline': max(row['max'], row['date_deadline'])
            }
        return res

    @api.depends('planned_date_begin', 'date_deadline', 'user_ids', 'allocated_hours')
    def _compute_planning_overlap(self):
        overlap_mapping = self._get_planning_overlap_per_task()
        if not overlap_mapping:
            self.planning_overlap = False
            return overlap_mapping
        user_ids = set()
        absolute_min_start = utc.localize(self[0].planned_date_begin or datetime.utcnow())
        absolute_max_end = utc.localize(self[0].date_deadline or datetime.utcnow())
        for task in self:
            for user_id, task_mapping in overlap_mapping.get(task.id, {}).items():
                absolute_min_start = min(absolute_min_start, utc.localize(task_mapping["min_planned_date_begin"]))
                absolute_max_end = max(absolute_max_end, utc.localize(task_mapping["max_date_deadline"]))
                user_ids.add(user_id)
        users = self.env['res.users'].browse(list(user_ids))

        regular_users_ids = []
        flexible_resources_ids = []
        flex_user_resource = {}
        flex_resource_user_id = {}
        for user in users:
            resource = user._get_project_task_resource()
            if resource and resource._is_flexible():
                flexible_resources_ids.append(resource.id)
                flex_user_resource[user.id] = resource
                flex_resource_user_id[resource.id] = user.id
            else:
                regular_users_ids.append(user.id)

        users_work_intervals, _dummy = self.env['res.users'].browse(regular_users_ids).sudo()._get_valid_work_intervals(absolute_min_start, absolute_max_end)
        flex_resources_work_intervals, flex_user_work_hours_per_day, flex_user_work_hours_per_week = self.env["resource.resource"].browse(flexible_resources_ids)._get_flexible_resource_valid_work_intervals(absolute_min_start, absolute_max_end)

        for resource_id, intervals in flex_resources_work_intervals.items():
            users_work_intervals[flex_resource_user_id[resource_id]] = intervals

        res = {}
        for task in self:
            overlap_messages = []
            for user_id, task_mapping in overlap_mapping.get(task.id, {}).items():
                task_intervals_start = utc.localize(task_mapping['min_planned_date_begin'])
                task_intervals_end = utc.localize(task_mapping['max_date_deadline'])
                task_intervals = Intervals([(task_intervals_start, task_intervals_end, self.env['resource.calendar.attendance'])])
                work_intervals = users_work_intervals[user_id] & task_intervals
                if resource := flex_user_resource.get(user_id):
                    work_hours = resource._get_flexible_resource_work_hours(work_intervals, flex_user_work_hours_per_day[resource.id], flex_user_work_hours_per_week[resource.id])
                else:
                    work_hours = sum_intervals(work_intervals)

                if task_mapping['sum_allocated_hours'] > work_hours:
                    overlap_messages.append(_(
                        '%(partner)s has %(amount)s tasks at the same time.',
                        partner=task_mapping["partner_name"],
                        amount=len(task_mapping['overlapping_tasks_ids']),
                    ))
                    if task.id not in res:
                        res[task.id] = {}
                    res[task.id][user_id] = task_mapping
            task.planning_overlap = ' '.join(overlap_messages) or False
        return res

    @api.model
    def _search_planning_overlap(self, operator, value):
        # search implemented only for 'in' {bool}
        if operator != 'in':
            return NotImplemented
        if not all(isinstance(v, bool) for v in value):
            return NotImplemented

        sql = SQL("""(
            SELECT T1.id
            FROM project_task T1
            INNER JOIN project_task T2 ON T1.id <> T2.id
            INNER JOIN project_task_user_rel U1 ON T1.id = U1.task_id
            INNER JOIN project_task_user_rel U2 ON T2.id = U2.task_id
                AND U1.user_id = U2.user_id
            WHERE
                T1.planned_date_begin < T2.date_deadline
                AND T1.date_deadline > T2.planned_date_begin
                AND T1.planned_date_begin IS NOT NULL
                AND T1.date_deadline IS NOT NULL
                AND T1.date_deadline > NOW() AT TIME ZONE 'UTC'
                AND T1.active = 't'
                AND T1.state IN ('01_in_progress', '02_changes_requested', '03_approved', '04_waiting_normal')
                AND T1.project_id IS NOT NULL
                AND T2.planned_date_begin IS NOT NULL
                AND T2.date_deadline IS NOT NULL
                AND T2.date_deadline > NOW() AT TIME ZONE 'UTC'
                AND T2.project_id IS NOT NULL
                AND T2.active = 't'
                AND T2.state IN ('01_in_progress', '02_changes_requested', '03_approved', '04_waiting_normal')
        )""")
        operator_new = 'in' if any(value) else 'not in'
        return [('id', operator_new, sql)]

    def _compute_user_names(self):
        for task in self:
            task.user_names = format_list(self.env, task.user_ids.mapped('name'))

    @api.model
    def _calculate_planned_dates(self, date_start, date_stop, user_id=None, calendar=None):
        if not (date_start and date_stop):
            raise UserError(_('One parameter is missing to use this method. You should give a start and end dates.'))
        start, stop = date_start, date_stop
        if isinstance(start, str):
            start = fields.Datetime.from_string(start)
        if isinstance(stop, str):
            stop = fields.Datetime.from_string(stop)

        if not calendar:
            user = self.env['res.users'].sudo().browse(user_id) if user_id and user_id != self.env.user.id else self.env.user
            calendar = user.resource_calendar_id or self.env.company.resource_calendar_id
            if not calendar:  # Then we stop and return the dates given in parameter.
                return date_start, date_stop

        if not start.tzinfo:
            start = start.replace(tzinfo=utc)
        if not stop.tzinfo:
            stop = stop.replace(tzinfo=utc)

        intervals = calendar._work_intervals_batch(start, stop)[False]
        if not intervals:  # Then we stop and return the dates given in parameter
            return date_start, date_stop
        list_intervals = [(start, stop) for start, stop, records in intervals]  # Convert intervals in interval list
        start = list_intervals[0][0].astimezone(utc).replace(tzinfo=None)  # We take the first date in the interval list
        stop = list_intervals[-1][1].astimezone(utc).replace(tzinfo=None)  # We take the last date in the interval list
        return start, stop

    def _get_tasks_by_resource_calendar_dict(self):
        """
            Returns a dict of:
                key = 'resource.calendar'
                value = recordset of 'project.task'
        """
        default_calendar = self.env.company.resource_calendar_id

        calendar_by_user_dict = {  # key: user_id, value: resource.calendar instance
            user.id:
                user.resource_calendar_id or default_calendar
            for user in self.mapped('user_ids')
        }

        tasks_by_resource_calendar_dict = defaultdict(
            lambda: self.env[self._name])  # key = resource_calendar instance, value = tasks
        for task in self:
            if len(task.user_ids) == 1:
                tasks_by_resource_calendar_dict[calendar_by_user_dict[task.user_ids.id]] |= task
            else:
                tasks_by_resource_calendar_dict[default_calendar] |= task

        return tasks_by_resource_calendar_dict

    @api.depends('planned_date_begin', 'depend_on_ids.date_deadline')
    def _compute_dependency_warning(self):
        if not (
            self._origin
            and (tasks_with_task_dependencies := self.filtered('allow_task_dependencies'))
        ):
            self.dependency_warning = False
            return

        (self - tasks_with_task_dependencies).dependency_warning = False
        self.flush_model(['planned_date_begin', 'date_deadline'])
        query = """
            SELECT t1.id,
                   ARRAY_AGG(t2.name) as depends_on_names
              FROM project_task t1
              JOIN task_dependencies_rel d
                ON d.task_id = t1.id
              JOIN project_task t2
                ON d.depends_on_id = t2.id
             WHERE t1.id IN %s
               AND t1.planned_date_begin IS NOT NULL
               AND t2.date_deadline IS NOT NULL
               AND t2.date_deadline > t1.planned_date_begin
          GROUP BY t1.id
	    """
        self.env.cr.execute(query, (tuple(tasks_with_task_dependencies.ids),))
        depends_on_names_for_id = {
            group['id']: group['depends_on_names']
            for group in self.env.cr.dictfetchall()
        }
        for task in tasks_with_task_dependencies:
            depends_on_names = depends_on_names_for_id.get(task.id)
            task.dependency_warning = depends_on_names and _(
                'This task cannot be planned before the following tasks on which it depends: %(task_list)s',
                task_list=depends_on_names,
            )

    @api.model
    def _search_dependency_warning(self, operator, value):
        # search implemented only for 'in' {bool}
        if operator != 'in':
            return NotImplemented
        if not all(isinstance(v, bool) for v in value):
            return NotImplemented

        sql = SQL("""
            SELECT t1.id
              FROM project_task t1
              JOIN task_dependencies_rel d
                ON d.task_id = t1.id
              JOIN project_task t2
                ON d.depends_on_id = t2.id
             WHERE t1.planned_date_begin IS NOT NULL
               AND t2.date_deadline IS NOT NULL
               AND t2.date_deadline > t1.planned_date_begin
        """)
        operator_new = 'in' if any(value) else 'not in'
        return [('id', operator_new, sql)]

    @api.depends('planned_date_begin', 'date_deadline')
    def _compute_planned_date_start(self):
        for task in self:
            task.planned_date_start = task.planned_date_begin or task.date_deadline

    def _inverse_planned_date_start(self):
        """ Inverse method only used for calendar view to update the date start if the date begin was defined """
        for task in self:
            if task.planned_date_begin:
                task.planned_date_begin = task.planned_date_start
            else:  # to keep the right hour in the date_deadline
                task.date_deadline = task.planned_date_start

    def _inverse_state(self):
        super()._inverse_state()
        self.filtered(
            lambda t:
                t.state == '1_canceled'
                and t.planned_date_begin
                and t.planned_date_begin > fields.Datetime.now()
        ).write({
            'planned_date_begin': False,
            'date_deadline': False,
        })

    def _search_planned_date_start(self, operator, value):
        return [
            '|',
            '&', ("planned_date_begin", "!=", False), ("planned_date_begin", operator, value),
            '&', '&', ("planned_date_begin", "=", False), ("date_deadline", "!=", False), ("date_deadline", operator, value),
        ]

    def write(self, vals):
        compute_default_planned_dates = None
        compute_allocated_hours = None
        date_start_update = 'planned_date_begin' in vals and vals['planned_date_begin'] is not False
        date_end_update = 'date_deadline' in vals and vals['date_deadline'] is not False
        # if fsm_mode=True then the processing in industry_fsm module is done for these dates.
        if date_start_update and date_end_update \
           and not any(task.planned_date_begin or task.date_deadline for task in self):
            if len(self) > 1:
                compute_default_planned_dates = self.filtered(lambda task: not task.planned_date_begin)
            if not vals.get('allocated_hours') and vals.get('planned_date_begin') and vals.get('date_deadline'):
                compute_allocated_hours = self.filtered(lambda task: not task.allocated_hours)

        # if date_end was set to False, so we set planned_date_begin to False
        if not vals.get('date_deadline', True):
            vals['planned_date_begin'] = False

        if compute_default_planned_dates:
            # Take the default planned dates
            planned_date_begin = vals.get('planned_date_begin', False)
            date_deadline = vals.get('date_deadline', False)

            # Then sort the tasks by resource_calendar and finally compute the planned dates
            tasks_by_resource_calendar_dict = compute_default_planned_dates.sudo()._get_tasks_by_resource_calendar_dict()
            for (calendar, tasks) in tasks_by_resource_calendar_dict.items():
                date_start, date_stop = self._calculate_planned_dates(planned_date_begin, date_deadline,
                                                                      calendar=calendar)
                vals['planned_date_begin'] = date_start
                vals['date_deadline'] = date_stop

        res = super().write(vals)

        # Get the tasks which are either not linked to a project or their project has not timesheet tracking
        tasks_without_timesheets_track = self.filtered(lambda task: (
            'allocated_hours' not in vals and
            (task.planned_date_begin and task.date_deadline) and
            ("allow_timesheet" in task.project_id and not task.project_id.allow_timesheet)
        ))
        if tasks_without_timesheets_track:
            tasks_without_timesheets_track._set_allocated_hours_for_tasks()

        if compute_allocated_hours:
            # 1) Calculate capacity for selected period
            start = fields.Datetime.from_string(vals['planned_date_begin'])
            stop = fields.Datetime.from_string(vals['date_deadline'])
            if not start.tzinfo:
                start = start.replace(tzinfo=utc)
            if not stop.tzinfo:
                stop = stop.replace(tzinfo=utc)

            resource = compute_allocated_hours.sudo().user_ids._get_project_task_resource()
            if len(resource) == 1 and resource.calendar_id:
                # First case : trying to plan tasks for a single user that has its own calendar => using user's calendar
                calendar = resource.calendar_id
                work_intervals = calendar._work_intervals_batch(start, stop, resources=resource)
                capacity = sum_intervals(work_intervals[resource.id])
            else:
                # Second case : trying to plan tasks for a single user that has no calendar / for multiple users => using company's calendar
                calendar = self.env.company.resource_calendar_id
                work_intervals = calendar._work_intervals_batch(start, stop)
                capacity = sum_intervals(work_intervals[False])

            # 2) Plan tasks without assignees
            tasks_no_assignees = compute_allocated_hours.filtered(lambda task: not task.user_ids)
            if tasks_no_assignees:
                if calendar == self.env.company.resource_calendar_id:
                    hours = capacity # we can avoid recalculating the amount here
                else:
                    calendar = self.env.company.resource_calendar_id
                    hours = sum_intervals(calendar._work_intervals_batch(start, stop)[False])
                tasks_no_assignees.write({"allocated_hours": hours})
            compute_allocated_hours -= tasks_no_assignees

            if compute_allocated_hours: # this recordset could be empty, and we don't want to divide by 0 when checking the length of it
                # 3) Remove the already set allocated hours from the capacity
                capacity -= sum((self - compute_allocated_hours).filtered(lambda task: task.allocated_hours and task.user_ids).mapped('allocated_hours'))

                # 4) Split capacity for every task and plan them
                if capacity > 0:
                    compute_allocated_hours.sudo().write({"allocated_hours": capacity / len(compute_allocated_hours)})

        return res

    def _set_allocated_hours_for_tasks(self):
        tasks_by_resource_calendar_dict = self._get_tasks_by_resource_calendar_dict()
        for (calendar, tasks) in tasks_by_resource_calendar_dict.items():
            # 1. Get the min start and max end among the tasks
            absolute_min_start, absolute_max_end = tasks[0].planned_date_begin, tasks[0].date_deadline
            for task in tasks:
                absolute_max_end = max(absolute_max_end, task.date_deadline)
                absolute_min_start = min(absolute_min_start, task.planned_date_begin)
            start = fields.Datetime.from_string(absolute_min_start)
            stop = fields.Datetime.from_string(absolute_max_end)
            if not start.tzinfo:
                start = start.replace(tzinfo=utc)
            if not stop.tzinfo:
                stop = stop.replace(tzinfo=utc)
            # 2. Fetch the working hours between min start and max end
            work_intervals = calendar._work_intervals_batch(start, stop)[False]
            # 3. For each task compute and write the allocated hours corresponding to their planned dates
            for task in tasks:
                start = task.planned_date_begin
                stop = task.date_deadline
                if not start.tzinfo:
                    start = start.replace(tzinfo=utc)
                if not stop.tzinfo:
                    stop = stop.replace(tzinfo=utc)
                allocated_hours = sum_intervals(work_intervals & Intervals([(start, stop, self.env['resource.calendar.attendance'])]))
                task.allocated_hours = allocated_hours

    def _get_additional_users(self, domain):
        return self.env['res.users']

    def _group_expand_user_ids(self, users, domain):
        """ Group expand by user_ids in gantt view :
            all users which have and open task in this project + the current user if not filtered by assignee
        """
        additional_users = self._get_additional_users(domain)
        if additional_users:
            return additional_users
        start_date = self.env.context.get('gantt_start_date')
        scale = self.env.context.get('gantt_scale')
        if not (start_date and scale):
            return additional_users
        domain = filter_domain_leaf(domain, lambda field: field not in ['planned_date_begin', 'date_deadline', 'state'])
        search_on_comodel = self._search_on_comodel(domain, "user_ids", "res.users")
        if search_on_comodel:
            return search_on_comodel
        start_date = fields.Datetime.from_string(start_date)
        delta = get_timedelta(1, scale)
        domain_expand = (
            Domain(self._group_expand_user_ids_domain([
                ('planned_date_begin', '>=', start_date - delta),
                ('date_deadline', '<', start_date + delta)
            ])) & domain
        )
        return self.search(domain_expand).user_ids.filtered(lambda user: user.active) | self.env.user

    def _group_expand_user_ids_domain(self, domain_expand):
        project_id = self.env.context.get('default_project_id')
        if project_id:
            domain_expand = Domain.OR([[
                ('project_id', '=', project_id),
                ('is_closed', '=', False),
                ('planned_date_begin', '=', False),
                ('date_deadline', '=', False),
            ], domain_expand])
        else:
            domain_expand = Domain.AND([[
                ('project_id', '!=', False),
            ], domain_expand])
        return domain_expand

    @api.model
    def _group_expand_project_ids(self, projects, domain):
        start_date = self.env.context.get('gantt_start_date')
        scale = self.env.context.get('gantt_scale')
        default_project_id = self.env.context.get('default_project_id')
        is_my_task = self.env.context.get('my_tasks')
        if not (start_date and scale) or default_project_id:
            return projects
        domain = self._expand_domain_dates(domain)
        # Check on filtered domain is necessary in case we are in the 'All tasks' menu
        # Indeed, the project_id != False default search would lead in a wrong result when
        # no other search have been made
        filtered_domain = list(filter_domain_leaf(domain, lambda field: field == "project_id"))
        search_on_comodel = self._search_on_comodel(domain, "project_id", "project.project")
        if search_on_comodel and (default_project_id or is_my_task or len(filtered_domain) > 1):
            return search_on_comodel
        return self.search(domain).project_id

    @api.model
    def _group_expand_partner_ids(self, partners, domain):
        start_date = self.env.context.get('gantt_start_date')
        scale = self.env.context.get('gantt_scale')
        if not (start_date and scale):
            return partners
        domain = self._expand_domain_dates(domain)
        search_on_comodel = self._search_on_comodel(domain, "partner_id", "res.partner")
        if search_on_comodel:
            return search_on_comodel
        return self.search(domain).partner_id

    def _expand_domain_dates(self, domain):
        filters = []
        for dom in domain:
            if len(dom) == 3 and dom[0] == 'date_deadline' and dom[1] == '>=':
                min_date = dom[2] if isinstance(dom[2], datetime) else datetime.strptime(dom[2], '%Y-%m-%d %H:%M:%S')
                min_date = min_date - get_timedelta(1, self.env.context.get('gantt_scale'))
                filters.append((dom[0], dom[1], min_date))
            else:
                filters.append(dom)
        return filters

    def _get_users_available_work_intervals(self, start_datetime, end_datetime):
        users_work_intervals, calendar_work_intervals = self.user_ids._get_valid_work_intervals(start_datetime, end_datetime)
        company = self.user_ids.company_id if self.user_ids.company_id.id else self.env.company
        company_work_intervals = calendar_work_intervals.get(company.resource_calendar_id.id, company.resource_calendar_id._work_intervals_batch(start_datetime, end_datetime)[False])
        available_work_intervals = None
        for user in self.user_ids:
            work_intervals = users_work_intervals.get(user.id)
            if not work_intervals:
                continue
            if available_work_intervals is None:
                available_work_intervals = work_intervals
            else:
                available_work_intervals &= work_intervals

        if not available_work_intervals:
            available_work_intervals = company_work_intervals
        return available_work_intervals

    def plan_task_in_calendar(self, vals):
        self.ensure_one()
        if planned_date_begin := vals.get("planned_date_begin"):
            tz_info = self.env.context.get('tz') or self.env.user.tz or 'UTC'
            planned_date_begin = datetime.strptime(planned_date_begin, '%Y-%m-%d %H:%M:%S').astimezone(timezone(tz_info))
            if self.allocated_hours:
                # expected days + one month in case the current user took some day offs in the future
                max_date_end = planned_date_begin + relativedelta(days=self.allocated_hours / 8, months=1)
                available_work_intervals = self._get_users_available_work_intervals(planned_date_begin, max_date_end)
                hours_to_plan = self.allocated_hours
                compute_date_end = None
                for start_date, end_date, _dummy in available_work_intervals:
                    hours_to_plan -= (end_date - start_date).total_seconds() / 3600
                    if hours_to_plan <= 0:
                        compute_date_end = end_date + relativedelta(seconds=hours_to_plan * 3600)
                        break
                if available_work_intervals:
                    if not compute_date_end:
                        compute_date_end = available_work_intervals._items[-1][1]
                    if self.env.context.get('task_calendar_plan_full_day'):
                        vals['planned_date_begin'] = available_work_intervals._items[0][0].astimezone(utc).replace(tzinfo=None)
                if compute_date_end:
                    vals['date_deadline'] = compute_date_end.astimezone(utc).replace(tzinfo=None)
            elif self.env.context.get('task_calendar_plan_full_day'):
                planned_date_begin += relativedelta(hour=0, minute=0, second=0, microsecond=0)
                planned_date_end = datetime.strptime(vals['date_deadline'], '%Y-%m-%d %H:%M:%S').astimezone(timezone(tz_info))
                planned_date_end += relativedelta(hour=23, minute=59, second=59, microsecond=59)
                available_work_intervals = self._get_users_available_work_intervals(planned_date_begin, planned_date_end)
                if available_work_intervals:
                    vals['planned_date_begin'] = available_work_intervals._items[0][0].astimezone(utc).replace(tzinfo=None)
                    vals['date_deadline'] = available_work_intervals._items[-1][1].astimezone(utc).replace(tzinfo=None)
        return super().plan_task_in_calendar(vals)

    # -------------------------------------
    # Business Methods : Smart Scheduling
    # -------------------------------------
    def schedule_tasks(self, vals):
        """ Compute the start and end planned date for each task in the recordset.

            This computation is made according to the schedule of the employee the tasks
            are assigned to, as well as the task already planned for the user.
            The function schedules the tasks order by dependencies, priority.
            The transitivity of the tasks is respected in the recordset, but is not guaranteed
            once the tasks are planned for some specific use case. This function ensures that
            no tasks planned by it are concurrent with another.
            If this function is used to plan tasks for the company and not an employee,
            the tasks are planned with the company calendar, and have the same starting date.
            Their end date is computed based on their timesheet only.
            Concurrent or dependent tasks are irrelevant.

            :return: empty dict if some data were missing for the computation
                or if no action and no warning to display.
                Else, return a dict { 'action': action, 'warnings'; warning_list } where action is
                the action to launch if some planification need the user confirmation to be applied,
                and warning_list the warning message to show if needed.
        """
        required_written_fields = {'planned_date_begin', 'date_deadline'}
        if not self.env.context.get('last_date_view') or any(key not in vals for key in required_written_fields):
            self.write(vals)
            return {}

        max_date_start = datetime.strptime(self.env.context.get('last_date_view'), '%Y-%m-%d %H:%M:%S')
        return self.sorted(
            lambda t: (not t.date_deadline, t.date_deadline, t._get_hours_to_plan() <= 0, -int(t.priority))
        )._scheduling(vals, max_date_start)

    def _get_dependencies_dict(self):
        # contains a task as key and the list of tasks before this one as values
        return {
            task:
                [t for t in task.depend_on_ids if t != task and t in self]
                if task.depend_on_ids
                else []
            for task in self
        }

    def _scheduling(self, vals, max_date_start, first_possible_date_per_task=None):
        if first_possible_date_per_task is None:
            first_possible_date_per_task = {}

        tasks_to_write = {}
        warnings = {}
        old_vals_per_task_id = {}

        company = self.company_id if len(self.company_id) == 1 else self.env.company
        tz_info = self.env.context.get('tz') or 'UTC'
        locale = babel_locale_parse(get_lang(self.env).code)

        user_to_assign = self.env['res.users']

        users = self.user_ids
        if vals.get('user_ids') and len(vals['user_ids']) == 1:
            user_to_assign = self.env['res.users'].browse(vals['user_ids'])
            if user_to_assign not in users:
                users |= user_to_assign
            tz_info = user_to_assign.tz or tz_info
        else:
            if (self.env.context.get("default_project_id")):
                project = self.env['project.project'].browse(self.env.context["default_project_id"])
                company = project.company_id if project.company_id else company
                calendar = project.resource_calendar_id
            else:
                calendar = company.resource_calendar_id
            tz_info = calendar.tz or tz_info

        date_start = datetime.strptime(vals["planned_date_begin"], '%Y-%m-%d %H:%M:%S').astimezone(timezone(tz_info))
        fetch_date_end = max_date_start.astimezone(timezone(tz_info))
        end_loop = date_start + relativedelta(day=31, month=12, years=1)  # end_loop will be the end of the next year.

        valid_intervals_per_user, flex_user_work_hours_per_day, flex_user_work_hours_per_week = self._web_gantt_get_valid_intervals(date_start, fetch_date_end, users, [], True)
        dependent_tasks_end_dates = self._fetch_last_date_end_from_dependent_task_for_all_tasks()

        first_possible_date_per_task = {
            key: max(
                first_possible_date_per_task.get(key, datetime.min),
                dependent_tasks_end_dates.get(key, datetime.min),
            ).astimezone(timezone(tz_info))
            for key in first_possible_date_per_task.keys() | dependent_tasks_end_dates.keys()
        }

        scale = self.env.context.get("gantt_scale", "week")
        # In week and month scale, the precision set is used. In day scale we force the half day precison.
        cell_part_from_context = self.env.context.get("cell_part")
        cell_part = cell_part_from_context if scale in ["week", "month"] and cell_part_from_context in [1, 2, 4] else 2
        # In year scale, cells represent a month, a typical full-time work schedule involves around 160 to 176 hours per month
        delta_hours = 160 if scale == "year" else 24 / cell_part

        sorted_tasks = topological_sort(self._get_dependencies_dict())
        for task in sorted_tasks:
            hours_to_plan = task._get_hours_to_plan()

            compute_date_start = compute_date_end = False
            first_possible_start_date = first_possible_date_per_task.get(task.id)

            user_ids = False
            if user_to_assign and user_to_assign not in task.user_ids:
                user_ids = tuple(user_to_assign.ids)
            elif task.user_ids:
                user_ids = tuple(task.user_ids.ids)

            if user_ids not in valid_intervals_per_user:
                if 'no_intervals' not in warnings:
                    warnings['no_intervals'] = _("Some tasks weren't planned because the closest available starting date was too far ahead in the future")
                continue

            if hours_to_plan <= 0:
                hours_to_plan = delta_hours

            if user_ids:
                hours_to_plan /= len(user_ids)

            while not compute_date_end or hours_to_plan > 0:
                used_intervals = []
                for start_date, end_date, _dummy in valid_intervals_per_user[user_ids]:
                    if first_possible_start_date:
                        if end_date <= first_possible_start_date:
                            continue

                        if first_possible_start_date > start_date:
                            start_date = first_possible_start_date

                    # for flexible resources, work intervals are divided (min time of the day, max time of the day)
                    # a microsecond is lost in the total duration and the end of the interval
                    # it's the only way to have many intervals, as if end date of a range = start date of the next range,
                    # both will be merged in one range
                    if end_date.time() == time.max:
                        end_date += relativedelta(microseconds=1)

                    day = start_date.date()
                    year_and_week = weeknumber(locale, day)
                    real_interval_duration = (end_date - start_date).total_seconds() / 3600
                    interval_duration = real_interval_duration
                    # start_date and end_date are the same day
                    # we check duration doesn't exceed work hours for flexible resources
                    for user_id in user_ids or ():
                        if user_id in flex_user_work_hours_per_day:
                            interval_duration = min(interval_duration, flex_user_work_hours_per_day[user_id].get(day, 0.0), flex_user_work_hours_per_week[user_id].get(year_and_week, 0.0))

                    if interval_duration <= 0.0:
                        continue

                    consumed_hours = interval_duration if hours_to_plan >= interval_duration else hours_to_plan
                    for user_id in user_ids or ():
                        if user_id in flex_user_work_hours_per_day:
                            flex_user_work_hours_per_day[user_id][day] -= consumed_hours
                            flex_user_work_hours_per_week[user_id][year_and_week] -= consumed_hours

                    hours_to_plan -= consumed_hours
                    if not compute_date_start:
                        compute_date_start = start_date

                    diff = real_interval_duration - consumed_hours
                    if diff > 0:
                        end_date -= relativedelta(hours=diff)

                    used_intervals.append((start_date, end_date, task))

                    if hours_to_plan == 0.0:
                        compute_date_end = end_date
                        break

                # Get more intervals if the fetched ones are not enough for scheduling
                if compute_date_end and hours_to_plan <= 0:
                    break

                if fetch_date_end < end_loop:
                    new_fetch_date_end = min(fetch_date_end + relativedelta(months=1), end_loop)
                    valid_intervals_per_user, flex_user_work_hours_per_day, flex_user_work_hours_per_week = self._web_gantt_get_valid_intervals(fetch_date_end, new_fetch_date_end, users, [], True, valid_intervals_per_user)
                    fetch_date_end = new_fetch_date_end
                else:
                    if 'no_intervals' not in warnings:
                        warnings['no_intervals'] = _("Some tasks weren't planned because the closest available starting date was too far ahead in the future")
                    break

            # remove the task from the record to avoid unnecessary write
            self -= task
            if not compute_date_end or hours_to_plan > 0:
                continue

            start_no_utc = compute_date_start.astimezone(utc).replace(tzinfo=None)
            end_no_utc = compute_date_end.astimezone(utc).replace(tzinfo=None)
            # if the working interval for the task has overlap with 'invalid_intervals', we set the warning message accordingly
            tasks_to_write[task] = {'start': start_no_utc, 'end': end_no_utc}

            for next_task in task.dependent_ids:
                first_possible_date_per_task[next_task.id] = max(first_possible_date_per_task.get(next_task.id, compute_date_end), compute_date_end)

            used_intervals = Intervals(used_intervals)
            if not user_ids:
                valid_intervals_per_user[False] -= used_intervals
            else:
                for user_id in valid_intervals_per_user:
                    if not user_id:
                        continue

                    if set(user_id) & set(user_ids):
                        valid_intervals_per_user[user_id] -= used_intervals

        for task in tasks_to_write:
            old_vals_per_task_id[task.id] = {
                'planned_date_begin': task.planned_date_begin,
                'date_deadline': task.date_deadline,
            }
            task_vals = {
                'planned_date_begin': tasks_to_write[task]['start'],
                'date_deadline': tasks_to_write[task]['end'],
            }
            if user_to_assign:
                old_user_ids = task.user_ids.ids
                if user_to_assign.id not in old_user_ids:
                    task_vals['user_ids'] = user_to_assign.ids
                    old_vals_per_task_id[task.id]['user_ids'] = old_user_ids or False

            task.write(task_vals)

        return [warnings, old_vals_per_task_id]

    def action_rollback_auto_scheduling(self, old_vals_per_task_id):
        for task in self:
            if str(task.id) in old_vals_per_task_id:
                task.write(old_vals_per_task_id[str(task.id)])

    def _get_hours_to_plan(self):
        return self.allocated_hours

    @api.model
    def _compute_schedule(self, user, calendar, date_start, date_end, company=None):
        """ Compute the working intervals available for the employee
            fill the empty schedule slot between contract with the company schedule.
        """
        if user:
            employees_work_days_data, dummy = user.sudo()._get_valid_work_intervals(date_start, date_end)
            schedule = employees_work_days_data.get(user.id) or Intervals([])
            # We are using this function to get the intervals for which the schedule of the employee is invalid. Those data are needed to check if we must fallback on the
            # company schedule. The validity_intervals['valid'] does not contain the work intervals needed, it simply contains large intervals with validity time period
            # ex of return value : ['valid'] = 01-01-2000 00:00:00 to 11-01-2000 23:59:59; ['invalid'] = 11-02-2000 00:00:00 to 12-31-2000 23:59:59
            dummy, validity_intervals = self._web_gantt_reschedule_get_resource_calendars_validity(
                date_start, date_end,
                resource=user._get_project_task_resource(),
                company=company)
            for start, stop, _dummy in validity_intervals['invalid']:
                schedule |= calendar._work_intervals_batch(start, stop)[False]

            return validity_intervals['invalid'], schedule
        else:
            return Intervals([]), calendar._work_intervals_batch(date_start, date_end)[False]

    def _fetch_last_date_end_from_dependent_task_for_all_tasks(self):
        """
            return: return a dict with task.id as key, and the latest date end from all the dependent task of that task
        """
        query = """
                    SELECT task.id as id,
                           MAX(depends_on.date_deadline) as date
                      FROM project_task task
                      JOIN task_dependencies_rel rel
                        ON rel.task_id = task.id
                      JOIN project_task depends_on
                        ON depends_on.id != all(%s)
                       AND depends_on.id = rel.depends_on_id
                       AND depends_on.date_deadline is not null
                     WHERE task.id = any(%s)
                  GROUP BY task.id
                """
        self.env.cr.execute(query, [self.ids, self.ids])
        return {res['id']: res['date'] for res in self.env.cr.dictfetchall()}

    @api.model
    def _fetch_concurrent_tasks_intervals_for_employee(self, date_begin, date_end, user, tz_info):
        concurrent_tasks = self.env['project.task']
        domain = [('user_ids', '=', user.id),
            ('date_deadline', '>=', date_begin),
            ('planned_date_begin', '<=', date_end),
        ]

        if user:
            concurrent_tasks = self.env['project.task'].search(
                domain,
                order='date_deadline',
            )

        return Intervals([
            (t.planned_date_begin.astimezone(timezone(tz_info)),
             t.date_deadline.astimezone(timezone(tz_info)),
             t)
            for t in concurrent_tasks
        ])

    def _check_concurrent_tasks(self, date_begin, date_end, concurrent_tasks):
        current_date_end = None
        for start, stop, _dummy in concurrent_tasks:
            if start <= date_end and stop >= date_begin:
                current_date_end = stop
            elif start > date_end:
                break
        return current_date_end

    def _get_end_interval(self, date, intervals):
        for start, stop, _dummy in intervals:
            if start <= date <= stop:
                return stop
        return date

    # -------------------------------------
    # Business Methods : Auto-shift
    # -------------------------------------
    def _get_tasks_durations(self, users, start_date_field_name, stop_date_field_name):
        """ task duration is computed as the sum of the durations of the intersections between [task planned_date_begin, task date_deadline]
            and valid_intervals of the user (if only one user is assigned) else valid_intervals of the company
        """
        if not self:
            return {}

        start_date = min(self.mapped(start_date_field_name))
        end_date = max(self.mapped(stop_date_field_name))
        valid_intervals_per_user, _dummy, _dummy = self._web_gantt_get_valid_intervals(start_date, end_date, users, [], False)

        duration_per_task = defaultdict(int)
        for task in self:
            if task.allocated_hours > 0:
                duration_per_task[task.id] = task.allocated_hours * 3600
                continue

            task_start, task_end = task[start_date_field_name].astimezone(utc), task[stop_date_field_name].astimezone(utc)
            user_id = (task.user_ids.id, ) if len(task.user_ids) == 1 else False
            work_intervals = valid_intervals_per_user.get(user_id, Intervals())
            for start, end, _dummy in work_intervals:
                start, end = start.astimezone(utc), end.astimezone(utc)
                if task_start < end and task_end > start:
                    duration_per_task[task.id] += (min(task_end, end) - max(task_start, start)).total_seconds()

            if task.id not in duration_per_task:
                duration_per_task[task.id] = (task.date_deadline - task.planned_date_begin).total_seconds()

        return duration_per_task

    def _web_gantt_reschedule_get_resource(self):
        """ Get the resource linked to the task. """
        self.ensure_one()
        return self.user_ids._get_project_task_resource() if len(self.user_ids) == 1 else self.env['resource.resource']

    def _web_gantt_reschedule_get_resource_entity(self):
        """ Get the resource entity linked to the task.
            The resource entity is either a company, either a resource to cope with resource invalidity
            (i.e. not under contract, not yet created...)
            This is used as key to keep information in the rescheduling business methods.
        """
        self.ensure_one()
        return self._web_gantt_reschedule_get_resource() or self.company_id or self.project_id.company_id

    def _web_gantt_reschedule_get_resource_calendars_validity(
            self, date_start, date_end, intervals_to_search=None, resource=None, company=None
    ):
        """ Get the calendars and resources (for instance to later get the work intervals for the provided date_start
            and date_end).

            :param date_start: A start date for the search
            :param date_end: A end date fot the search
            :param intervals_to_search: If given, the periods for which the calendars validity must be retrieved.
            :param resource: If given, it overrides the resource in self._get_resource
            :return: a dict `resource_calendar_validity` with calendars as keys and their validity as values,
                     a dict `resource_validity` with 'valid' and 'invalid' keys, with the intervals where the resource
                     has a valid calendar (resp. no calendar)
            :rtype: tuple(defaultdict(), dict())
        """
        interval = Intervals([(date_start, date_end, self.env['resource.calendar.attendance'])])
        if intervals_to_search:
            interval &= intervals_to_search
        invalid_interval = interval
        resource = self._web_gantt_reschedule_get_resource() if resource is None else resource
        default_company = company or self.company_id or self.project_id.company_id
        resource_calendar_validity = resource.sudo()._get_calendars_validity_within_period(
            date_start, date_end, default_company=default_company
        )[resource.id]
        for calendar in resource_calendar_validity:
            resource_calendar_validity[calendar] &= interval
            invalid_interval -= resource_calendar_validity[calendar]
        resource_validity = {
            'valid': interval - invalid_interval,
            'invalid': invalid_interval,
        }
        return resource_calendar_validity, resource_validity

    def _web_gantt_get_users_unavailable_intervals(self, user_ids, date_begin, date_end, tasks_to_exclude_ids):
        """
        Get the unavailable intervals per user, intervals already occupied by other tasks.

        :param user_ids: A list of user IDs for whom the unavailable intervals are being calculated.
        :param date_begin: The beginning date of the intervals.
        :param date_end: The end date of the intervals.
        :param tasks_to_exclude_ids: A list of task IDs to exclude from the already planned tasks.
        :return: A dictionary where the keys are user IDs and the values are the unavailable intervals.
        :rtype: dict[int, Intervals]
        """
        domain = [
            ('user_ids', 'in', user_ids),
            ('date_deadline', '>=', date_begin.replace(tzinfo=None)),
            ('planned_date_begin', '<=', date_end.replace(tzinfo=None)),
        ]

        if tasks_to_exclude_ids:
            domain.append(('id', 'not in', tasks_to_exclude_ids))

        already_planned_tasks = self.env['project.task'].search(domain, order='date_deadline')
        unavailable_intervals_per_user_id = defaultdict(list)
        for task in already_planned_tasks:
            interval_vals = (
                task.planned_date_begin.astimezone(utc),
                task.date_deadline.astimezone(utc),
                task
            )
            for user_id in task.user_ids.ids:
                unavailable_intervals_per_user_id[user_id].append(interval_vals)

        return {user_id: Intervals(vals) for user_id, vals in unavailable_intervals_per_user_id.items()}

    def _web_gantt_get_valid_intervals(self, start_date, end_date, users, candidates_ids=[], remove_intervals_with_planned_tasks=True, valid_intervals_per_user=None):
        """
        Get the valid intervals available for planning.

        :param start_date: The start date for the intervals.
        :param end_date: The end date for the intervals.
        :param users: A list of users for whom the intervals are being calculated.
        :param candidates_ids: A list of candidate IDs to plan.
        :param remove_intervals_with_planned_tasks: Whether to remove intervals with already planned tasks.
        :return: A tuple containing:

            - valid_intervals_per_user: A dictionary where keys are user IDs and values are lists of valid intervals.
            - flex_user_work_hours_per_day: A dictionary where keys are flexible resources users IDs and values are dicts,
            keys are days and values are number of available hours per day.

        :rtype: tuple(dict[int, List[Interval]], dict[int, dict[date, float]])
        """
        if not self:
            return {}, {}, {}

        flex_resource_user = {}
        flex_resources_ids = set()
        regular_resources_users_ids = set()
        for user in users:
            resource = user._get_project_task_resource()
            if resource and resource._is_flexible():
                flex_resource_user[resource.id] = user.id
                flex_resources_ids.add(resource.id)
            else:
                regular_resources_users_ids.add(user.id)

        regular_resources_users = self.env["res.users"].browse(regular_resources_users_ids)
        original_start_date, original_end_date = start_date.astimezone(utc), end_date.astimezone(utc)
        start_date, end_date = original_start_date, original_end_date

        flex_resources = self.env["resource.resource"].browse(flex_resources_ids)
        flex_resources_work_intervals, hours_per_day, hours_per_week = flex_resources._get_flexible_resource_valid_work_intervals(start_date, end_date)
        users_work_intervals, calendar_work_intervals = regular_resources_users.sudo()._get_valid_work_intervals(start_date, end_date)

        locale = babel_locale_parse(get_lang(self.env).code)
        if flex_resources:
            start_date = weekstart(locale, start_date)
            end_date = weekend(locale, end_date)

        unavailable_intervals = self._web_gantt_get_users_unavailable_intervals(users.ids, start_date, end_date, candidates_ids) if remove_intervals_with_planned_tasks else {}

        flex_user_work_hours_per_day = {}
        flex_user_work_hours_per_week = {}
        for resource in flex_resources:
            user_id = flex_resource_user[resource.id]
            users_work_intervals[user_id] = flex_resources_work_intervals[resource.id]

            if not resource._is_fully_flexible():
                flex_user_work_hours_per_day[user_id] = hours_per_day[resource.id]
                flex_user_work_hours_per_week[user_id] = hours_per_week[resource.id]

            if user_id not in unavailable_intervals:
                continue

            unavailable_intervals_day_formatted = unavailable_intervals[user_id] & flex_resources_work_intervals[resource.id]
            for interval in unavailable_intervals_day_formatted:
                tasks = interval[2]
                # start and end of intervals are on the same day thanks to flex_resources_work_intervals format
                day = interval[0].date()

                interval_allocated_hours = 0.0
                for task in tasks:
                    interval_as_Interval = Intervals([(interval[0].astimezone(pytz.utc).replace(tzinfo=None), interval[1].astimezone(pytz.utc).replace(tzinfo=None), set())])
                    interval_task_intersection = interval_as_Interval & Intervals([(task.planned_date_begin, task.date_deadline, set())])
                    interval_duration = sum_intervals(interval_task_intersection)
                    task_total_duration = (task.date_deadline - task.planned_date_begin).total_seconds() / 3600
                    rate = interval_duration / task_total_duration
                    interval_allocated_hours = rate * task.allocated_hours if task.allocated_hours else interval_duration / 3600
                    interval_allocated_hours_per_user = interval_allocated_hours / len(task.user_ids)
                    if day in flex_user_work_hours_per_day[user_id]:
                        flex_user_work_hours_per_day[user_id][day] -= interval_allocated_hours_per_user

                    year_and_week = weeknumber(locale, day)
                    flex_user_work_hours_per_week[user_id][year_and_week] -= interval_allocated_hours_per_user

        baseInterval = Intervals([(original_start_date, original_end_date, self.env['resource.calendar.attendance'])])
        new_valid_intervals_per_user = {}
        invalid_intervals_per_user = {}
        for user_id, work_intervals in users_work_intervals.items():
            _id = (user_id,)
            new_valid_intervals_per_user[_id] = work_intervals - unavailable_intervals.get(user_id, Intervals())
            invalid_intervals_per_user[_id] = baseInterval - new_valid_intervals_per_user[_id]

        company_id = users.company_id if len(users.company_id) == 1 else self.env.company
        company_calendar_id = company_id.resource_calendar_id
        company_work_intervals = calendar_work_intervals.get(company_calendar_id.id)
        if not company_work_intervals:
            new_valid_intervals_per_user[False] = company_calendar_id.sudo()._work_intervals_batch(original_start_date, original_end_date)[False]
        else:
            new_valid_intervals_per_user[False] = company_work_intervals

        for task in self:
            user_ids = tuple(task.user_ids.ids)
            if len(user_ids) < 2 or user_ids in new_valid_intervals_per_user:
                continue

            new_valid_intervals_per_user[user_ids] = new_valid_intervals_per_user[False]
            for user_id in user_ids:
                # if user is not present in invalid_intervals => he's not present in users_work_intervals
                # => he's not available at all and the users together don't have any valid interval in commun
                if (user_id, ) not in invalid_intervals_per_user:
                    new_valid_intervals_per_user[user_ids] = Intervals()
                    break

                new_valid_intervals_per_user[user_ids] -= invalid_intervals_per_user.get((user_id, ))

        if not valid_intervals_per_user:
            valid_intervals_per_user = new_valid_intervals_per_user
        else:
            for user_ids in new_valid_intervals_per_user:
                if user_ids in valid_intervals_per_user:
                    valid_intervals_per_user[user_ids] |= new_valid_intervals_per_user[user_ids]
                else:
                    valid_intervals_per_user[user_ids] = new_valid_intervals_per_user[user_ids]

        return valid_intervals_per_user, flex_user_work_hours_per_day, flex_user_work_hours_per_week

    def _get_new_dates(self,
        valid_intervals_per_user,
        users_ids,
        search_forward,
        first_possible_start_date_per_candidate,
        last_possible_end_date_per_candidate,
        candidate_duration,
        move_in_conflicts_users=None
    ):
        """ this method is used for 2 goals:
            - compute the new dates for a task to plan, users_ids is the task users
            - compute the start and date dates of the buffer for maintain buffer strategy, users_ids is False
            if the 2 tasks have differents users (we follow the company calendar) else the assigned users
        """
        if move_in_conflicts_users is None:
            move_in_conflicts_users = set()

        intervals = valid_intervals_per_user[users_ids]._items
        intervals_durations = 0
        step = 1 if search_forward else -1
        index = 0 if search_forward else len(intervals) - 1
        used_intervals = []
        compute_start_date, compute_end_date = False, False
        while users_ids not in move_in_conflicts_users and ((search_forward and index < len(intervals)) or (not search_forward and index >= 0)) and candidate_duration > intervals_durations:
            start, end, _dummy = intervals[index]
            index += step

            if search_forward:
                first_date = first_possible_start_date_per_candidate.get(self.id)
                if first_date and end <= first_date:
                    continue

                if not compute_start_date:
                    if first_date:
                        start = max(start, first_date)
                    compute_start_date = start

                compute_end_date = end
            else:
                last_date = last_possible_end_date_per_candidate.get(self.id)
                if last_date and start >= last_date:
                    continue

                if not compute_end_date:
                    if last_date:
                        end = min(end, last_date)
                    compute_end_date = end

                compute_start_date = start

            duration = (end - start).total_seconds()
            if intervals_durations + duration > candidate_duration:
                remaining = intervals_durations + duration - candidate_duration
                duration -= remaining
                if search_forward:
                    end += timedelta(seconds=-remaining)
                    compute_end_date = end
                else:
                    start += timedelta(seconds=remaining)
                    compute_start_date = start

            intervals_durations += duration
            used_intervals.append((start, end, self))

        return (used_intervals, intervals_durations, compute_start_date, compute_end_date)

    def _web_gantt_update_next_candidates_dates(self,
        dependency_field_name,
        dependency_inverted_field_name,
        search_forward,
        consume_buffer,
        start_date_field_name,
        stop_date_field_name,
        first_possible_start_date_per_candidate,
        last_possible_end_date_per_candidate,
        old_planned_date_begin,
        old_date_deadline,
        compute_start_date,
        compute_end_date,
        valid_intervals_per_user,
        valid_intervals_per_user_for_buffer_computes
    ):
        next_candidates = self[dependency_inverted_field_name if search_forward else dependency_field_name]
        for task in next_candidates:
            if not task._web_gantt_reschedule_is_record_candidate(start_date_field_name, stop_date_field_name):
                continue

            if search_forward:
                compute_end_date = compute_end_date.astimezone(utc)
                first_possible_start_date_per_candidate[task.id] = max(first_possible_start_date_per_candidate.get(task.id, compute_end_date), compute_end_date)
                if not consume_buffer and task[start_date_field_name] > old_date_deadline:
                    # follow users calendar if both taks belong to same users or follow company calendar
                    calendar_owner = tuple(self.user_ids.ids) if self.user_ids and self.user_ids == task.user_ids else False
                    seconds_between_tasks = sum_intervals(Intervals([(old_date_deadline.astimezone(utc), task[start_date_field_name].astimezone(utc), self.env['resource.calendar.attendance'])]) & valid_intervals_per_user_for_buffer_computes.get(calendar_owner, Intervals())) * 3600
                    if seconds_between_tasks > 0:
                        _dummy, buffer_duration, _dummy, buffer_end_date = task._get_new_dates(valid_intervals_per_user, calendar_owner, search_forward, first_possible_start_date_per_candidate, last_possible_end_date_per_candidate, seconds_between_tasks)
                        if not buffer_end_date or buffer_duration < seconds_between_tasks:
                            return False
                        first_possible_start_date_per_candidate[task.id] = max(first_possible_start_date_per_candidate[task.id], buffer_end_date)
            else:
                compute_start_date = compute_start_date.astimezone(utc)
                last_possible_end_date_per_candidate[task.id] = min(last_possible_end_date_per_candidate.get(task.id, compute_start_date), compute_start_date)
                if not consume_buffer and task[stop_date_field_name] < old_planned_date_begin:
                    # follow users calendar if both taks belong to same users or follow company calendar
                    calendar_owner = tuple(self.user_ids.ids) if self.user_ids and self.user_ids == task.user_ids else False
                    seconds_between_tasks = sum_intervals(Intervals([(task[stop_date_field_name].astimezone(utc), old_planned_date_begin.astimezone(utc), self.env['resource.calendar.attendance'])]) & valid_intervals_per_user_for_buffer_computes.get(calendar_owner, Intervals())) * 3600

                    if seconds_between_tasks > 0:
                        _dummy, buffer_duration, buffer_start_date, _dummy = task._get_new_dates(valid_intervals_per_user, calendar_owner, search_forward, first_possible_start_date_per_candidate, last_possible_end_date_per_candidate, seconds_between_tasks)
                        if not buffer_start_date or buffer_duration < seconds_between_tasks:
                            return False
                        last_possible_end_date_per_candidate[task.id] = min(last_possible_end_date_per_candidate[task.id], buffer_start_date)

        return True

    def _web_gantt_get_valid_intervals_for_buffer(self, candidates_ids, start_date_field_name, stop_date_field_name, users, consume_buffer):
        if consume_buffer:
            return {}

        all_candidates = self.browse(candidates_ids)

        buffer_start_date = min(all_candidates.filtered(start_date_field_name).mapped(start_date_field_name)).astimezone(utc)
        buffer_end_date = max(all_candidates.filtered(stop_date_field_name).mapped(stop_date_field_name)).astimezone(utc)
        return all_candidates._web_gantt_get_valid_intervals(buffer_start_date, buffer_end_date, users)[0]

    def _web_gantt_move_candidates(self, start_date_field_name, stop_date_field_name, dependency_field_name, dependency_inverted_field_name, search_forward, candidates_ids, consume_buffer, vals):
        self.ensure_one()
        tz_info = self.env.context.get('tz') or 'UTC'

        old_vals_per_pill_id = self.web_gantt_init_old_vals_per_pill_id(vals)
        if 'user_ids' in vals:
            new_user = vals['user_ids']
            old_user_ids = self.user_ids.ids
            if not new_user:
                vals['user_ids'] = False
            else:
                user_to_assign = self.env['res.users'].browse(new_user)
                if user_to_assign.id not in old_user_ids:
                    vals["user_ids"] = user_to_assign.ids

                tz_info = user_to_assign.tz or tz_info

            old_vals_per_pill_id[self.id]['user_ids'] = old_user_ids or False

        result = {
            "errors": [],
            "warnings": [],
        }

        candidates = self.browse([id for id in candidates_ids if id != self.id])
        users = candidates.user_ids.sudo()

        valid_intervals_per_user_for_buffer_computes = self._web_gantt_get_valid_intervals_for_buffer(candidates_ids, start_date_field_name, stop_date_field_name, users, consume_buffer)
        self.write(vals)

        if search_forward:
            start_date = self[stop_date_field_name]
            # 53 weeks = 1 year is estimated enough to plan a project (no valid proof)
            end_date = start_date + timedelta(weeks=53)
        else:
            end_date = self[start_date_field_name]
            start_date = max(datetime.now(), end_date - timedelta(weeks=53))
            if end_date <= start_date:
                result["errors"].append("past_error")
                return result, {}

        valid_intervals_per_user, _dummy, _dummy = candidates._web_gantt_get_valid_intervals(start_date, end_date, users, candidates.ids)
        initial_valid_intervals_per_user = dict(valid_intervals_per_user.items())

        move_in_conflicts_users = set()
        first_possible_start_date_per_candidate, last_possible_end_date_per_candidate = candidates._web_gantt_get_first_and_last_possible_dates(dependency_field_name, dependency_inverted_field_name, search_forward, stop_date_field_name, start_date_field_name)

        candidates_moved_with_conflicts = False
        candidates_passed_initial_deadline = False
        candidates_durations = candidates._get_tasks_durations(users, start_date_field_name, stop_date_field_name)

        update_next_candidates_dates_response = self._web_gantt_update_next_candidates_dates(dependency_field_name, dependency_inverted_field_name, search_forward, consume_buffer, start_date_field_name, stop_date_field_name,
            first_possible_start_date_per_candidate, last_possible_end_date_per_candidate, old_vals_per_pill_id[self.id][start_date_field_name], old_vals_per_pill_id[self.id][stop_date_field_name],
            self[start_date_field_name], self[stop_date_field_name], valid_intervals_per_user, valid_intervals_per_user_for_buffer_computes
        )

        if not update_next_candidates_dates_response:
            result["errors"].append("no_intervals_error")
            return result, {}

        for candidate in candidates:
            if consume_buffer and not candidate._web_gantt_is_candidate_in_conflict(start_date_field_name, stop_date_field_name, dependency_field_name, dependency_inverted_field_name):
                continue

            candidate_duration = candidates_durations[candidate.id]
            users = candidate.user_ids
            users_ids = tuple(users.ids) if users else False

            if users_ids not in valid_intervals_per_user:
                result["errors"].append("no_intervals_error")
                return result, {}

            used_intervals, intervals_durations, compute_start_date, compute_end_date = candidate._get_new_dates(valid_intervals_per_user, users_ids, search_forward, first_possible_start_date_per_candidate, last_possible_end_date_per_candidate, candidate_duration, move_in_conflicts_users)

            if users_ids not in move_in_conflicts_users and candidate_duration == intervals_durations and compute_start_date and compute_end_date:
                candidates_passed_initial_deadline = candidates_passed_initial_deadline or (not candidate[start_date_field_name] and compute_end_date > candidate[stop_date_field_name].astimezone(utc))
                old_planned_date_begin, old_date_deadline = candidate[start_date_field_name], candidate[stop_date_field_name]
                if candidate._web_gantt_reschedule_write_new_dates(compute_start_date, compute_end_date, start_date_field_name, stop_date_field_name):
                    old_vals_per_pill_id[candidate.id] = {
                        "planned_date_begin": old_planned_date_begin,
                        "date_deadline": old_date_deadline,
                    }
                else:
                    result["errors"].append("past_error")
                    return result, {}
            else:
                """ no more intervals and we haven't reached the duration to plan the candidate (pill)
                    plan in the first interval, this will lead to creating conflicts, so a notif is added
                    to notify the user
                """
                if users_ids not in initial_valid_intervals_per_user or len(initial_valid_intervals_per_user[users_ids]._items) == 0:
                    result["errors"].append("no_intervals_error")
                    return result, {}

                candidates_moved_with_conflicts = True
                move_in_conflicts_users.add(users_ids)
                final_interval_index = -1 if search_forward else 0
                ranges = initial_valid_intervals_per_user[users_ids]._items
                compute_start_date = ranges[final_interval_index][0]
                compute_end_date = ranges[final_interval_index][1]
                needed_intervals_duration = 0
                searching_step = -1 if search_forward else 1
                searching_index = len(ranges) if search_forward else -1
                while ((search_forward and searching_index - 1 > 0) or (not search_forward and searching_index + 1 < len(ranges))) and candidate_duration > needed_intervals_duration:
                    searching_index += searching_step
                    start, end, _dummy = ranges[searching_index]
                    start, end = start.astimezone(utc), end.astimezone(utc)
                    if search_forward:
                        compute_start_date = start
                    else:
                        compute_end_date = end

                    needed_intervals_duration += (end - start).total_seconds()

                if candidate_duration <= needed_intervals_duration:
                    remaining = needed_intervals_duration - candidate_duration

                    if search_forward:
                        compute_start_date += timedelta(seconds=remaining)
                    else:
                        compute_end_date += timedelta(seconds=-remaining)
                elif candidate_duration > needed_intervals_duration:
                    needed = candidate_duration - needed_intervals_duration
                    if search_forward:
                        compute_start_date += timedelta(seconds=-needed)
                    else:
                        compute_end_date += timedelta(seconds=needed)

                old_planned_date_begin, old_date_deadline = candidate[start_date_field_name], candidate[stop_date_field_name]
                if candidate._web_gantt_reschedule_write_new_dates(compute_start_date, compute_end_date, start_date_field_name, stop_date_field_name):
                    old_vals_per_pill_id[candidate.id] = {
                        "planned_date_begin": old_planned_date_begin,
                        "date_deadline": old_date_deadline,
                    }
                else:
                    result["errors"].append("past_error")
                    return result, {}

            update_next_candidates_dates_response = candidate._web_gantt_update_next_candidates_dates(dependency_field_name, dependency_inverted_field_name, search_forward, consume_buffer, start_date_field_name, stop_date_field_name,
                first_possible_start_date_per_candidate, last_possible_end_date_per_candidate, old_planned_date_begin, old_date_deadline, compute_start_date, compute_end_date, valid_intervals_per_user, valid_intervals_per_user_for_buffer_computes
            )
            if not update_next_candidates_dates_response:
                result["errors"].append("no_intervals_error")
                return result, {}

            used_intervals = Intervals(used_intervals)
            if not users_ids:
                valid_intervals_per_user[False] -= used_intervals
            else:
                users_ids_set = set(users_ids)
                for user in valid_intervals_per_user:
                    if not user:
                        continue

                    if not users_ids_set.isdisjoint(user):
                        valid_intervals_per_user[user] -= used_intervals

        if candidates_passed_initial_deadline:
            result["warnings"].append("initial_deadline")
        if candidates_moved_with_conflicts:
            result["warnings"].append("conflict")
        return result, old_vals_per_pill_id

    def _web_gantt_record_has_dependencies(self):
        self.ensure_one()
        return self.project_id.allow_task_dependencies

    def _web_gantt_reschedule_can_record_be_rescheduled(self, start_date_field_name, stop_date_field_name):
        self.ensure_one()
        return super()._web_gantt_reschedule_can_record_be_rescheduled(start_date_field_name, stop_date_field_name) and not self.is_closed

    def _web_gantt_reschedule_is_record_candidate(self, start_date_field_name, stop_date_field_name):
        """ Get whether the record is a candidate for the rescheduling. This method is meant to be overridden when
            we need to add a constraint in order to prevent some records to be rescheduled. This method focuses on the
            record itself

            :param start_date_field_name: The start date field used in the gantt view.
            :param stop_date_field_name: The stop date field used in the gantt view.
            :return: True if record can be rescheduled, False if not.
            :rtype: bool
        """
        self.ensure_one()
        return super()._web_gantt_reschedule_is_record_candidate(start_date_field_name, stop_date_field_name) and self._web_gantt_record_has_dependencies()

    def _web_gantt_get_reschedule_message_per_key(self, key, params=None):
        message = super()._web_gantt_get_reschedule_message_per_key(key, params)
        if message:
            return message

        if key == "no_intervals_error":
            return _("The tasks could not be rescheduled due to the assignees' lack of availability at this time.")
        elif key == "initial_deadline":
            return _("Some tasks were planned after their initial deadline.")
        elif key == "conflict":
            return _("Some tasks were scheduled concurrently, resulting in a conflict due to the limited availability of the assignees. The planned dates for these tasks may not align with their allocated hours.")
        else:
            return ""

    # ----------------------------------------------------
    # Overlapping tasks
    # ----------------------------------------------------

    def action_fsm_view_overlapping_tasks(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('project.action_view_all_task')
        if 'views' in action:
            gantt_view = self.env.ref("project_enterprise.project_task_dependency_view_gantt")
            map_view = self.env.ref('project_enterprise.project_task_map_view_no_title')
            action['views'] = [(gantt_view.id, 'gantt'), (map_view.id, 'map')] + [(state, view) for state, view in action['views'] if view not in ['gantt', 'map']]
        name = _('Tasks in Conflict')
        action.update({
            'display_name': name,
            'name': name,
            'domain' : [
                ('user_ids', 'in', self.user_ids.ids),
            ],
            'context': {
                'fsm_mode': False,
                'task_nameget_with_hours': False,
                'initialDate': self.planned_date_begin,
                'search_default_conflict_task': True,
            }
        })
        return action

    # ----------------------------------------------------
    # Gantt view
    # ----------------------------------------------------

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        resources = self.env['resource.resource']
        if field in ['user_ids', 'user_id']:
            resources = self.env['resource.resource'].search([('user_id', 'in', res_ids), ('company_id', 'in', self.env.companies.ids)], order='create_date')
        # we reverse sort the resources by date to keep the first one created in the dictionary
        # to anticipate the case of a resource added later for the same employee and company
        user_resource_mapping = {resource.user_id.id: resource.id for resource in resources}
        leaves_mapping = resources._get_unavailable_intervals(start, stop)
        company_calendar = self.env.company.resource_calendar_id
        company_leaves = [] if company_calendar.flexible_hours else company_calendar._unavailable_intervals(start.replace(tzinfo=utc), stop.replace(tzinfo=utc))

        cell_dt = timedelta(hours=1) if scale in ['day', 'week'] else timedelta(hours=12)

        result = {}
        for user_id in res_ids + [False]:
            resource_id = user_resource_mapping.get(user_id)
            calendar = leaves_mapping.get(resource_id, company_leaves)
            # remove intervals smaller than a cell, as they will cause half a cell to turn grey
            # ie: when looking at a week, a employee start everyday at 8, so there is a unavailability
            # like: 2019-05-22 20:00 -> 2019-05-23 08:00 which will make the first half of the 23's cell grey
            notable_intervals = filter(lambda interval: interval[1] - interval[0] >= cell_dt, calendar)
            result[user_id] = [{'start': interval[0], 'stop': interval[1]} for interval in notable_intervals]

        return result

    def web_gantt_write(self, data):
        res = True

        if any(
            f_name in self._fields and self._fields[f_name].type == 'many2many' and value and len(value) == 1
            for f_name, value in data.items()
        ):
            record_ids_per_m2m_field_names = defaultdict(list)
            full_write_record_ids = []
            for record in self:
                fields_to_remove = []
                for f_name, value in data.items():
                    if (
                        value
                        and f_name in record._fields
                        and record._fields[f_name].type == 'many2many'
                        and len(value) == 1
                        and value[0] in record[f_name].ids
                    ):
                        fields_to_remove.append(f_name)
                if fields_to_remove:
                    record_ids_per_m2m_field_names[tuple(fields_to_remove)].append(record.id)
                else:
                    full_write_record_ids.append(record.id)
            if record_ids_per_m2m_field_names:
                if full_write_record_ids:
                    res &= self.browse(full_write_record_ids).write(data)
                for fields_to_remove_from_data, record_ids in record_ids_per_m2m_field_names.items():
                    res &= self.browse(record_ids).write({
                        f_name: value
                        for f_name, value in data.items()
                        if f_name not in fields_to_remove_from_data
                    })
            else:
                res &= self.write(data)
        else:
            res &= self.write(data)

        return res

    def action_dependent_tasks(self):
        action = super().action_dependent_tasks()
        action['view_mode'] = 'list,form,kanban,calendar,pivot,graph,gantt,activity,map'
        return action

    def action_recurring_tasks(self):
        action = super().action_recurring_tasks()
        action['view_mode'] = 'list,form,kanban,calendar,pivot,graph,gantt,activity,map'
        return action

    def _gantt_progress_bar_user_ids(self, res_ids, start, stop):
        start_naive, stop_naive = start.replace(tzinfo=None), stop.replace(tzinfo=None)
        users = self.env['res.users'].search([('id', 'in', res_ids)])
        self.env['project.task'].check_access('read')

        project_tasks = self.env['project.task'].sudo().search([
            ('user_ids', 'in', res_ids),
            ('planned_date_begin', '<=', stop_naive),
            ('date_deadline', '>=', start_naive),
        ])
        project_tasks = project_tasks.with_context(prefetch_fields=False)
        # Prefetch fields from database to avoid doing one query by __get__.
        project_tasks.fetch(['planned_date_begin', 'date_deadline', 'user_ids'])
        allocated_hours_mapped = defaultdict(float)
        # Get the users work intervals between start and end dates of the gantt view
        users_work_intervals, dummy = users.sudo()._get_valid_work_intervals(start, stop)
        allocated_hours_mapped = project_tasks._allocated_hours_per_user_for_scale(users, start, stop)
        # Compute employee work hours based on its work intervals.
        work_hours = {
            user_id: sum_intervals(work_intervals)
            for user_id, work_intervals in users_work_intervals.items()
        }
        return {
            user.id: {
                'value': allocated_hours_mapped[user.id],
                'max_value': work_hours.get(user.id, 0.0),
            }
            for user in users
        }

    def _allocated_hours_per_user_for_scale(self, users, start, stop):
        absolute_max_end, absolute_min_start = stop, start
        allocated_hours_mapped = defaultdict(float)
        for task in self:
            absolute_max_end = max(absolute_max_end, utc.localize(task.date_deadline))
            absolute_min_start = min(absolute_min_start, utc.localize(task.planned_date_begin))
        users_work_intervals, _dummy = users.sudo()._get_valid_work_intervals(absolute_min_start, absolute_max_end)
        for task in self:
            task_date_begin = utc.localize(task.planned_date_begin)
            task_deadline = utc.localize(task.date_deadline)
            max_start = max(start, task_date_begin)
            min_end = min(stop, task_deadline)
            for user in task.user_ids:
                work_intervals_for_scale = sum_intervals(users_work_intervals[user.id] & Intervals([(max_start, min_end, self.env['resource.calendar.attendance'])]))
                work_intervals_for_task = sum_intervals(users_work_intervals[user.id] & Intervals([(task_date_begin, task_deadline, self.env['resource.calendar.attendance'])]))
                # The ratio between the workable hours in the gantt view scale and the workable hours
                # between start and end dates of the task allows to determine the allocated hours for the current scale
                ratio = 1
                if work_intervals_for_task:
                    ratio = work_intervals_for_scale / work_intervals_for_task
                allocated_hours_mapped[user.id] += (task.allocated_hours / len(task.user_ids)) * ratio

        return allocated_hours_mapped

    def _gantt_progress_bar(self, field, res_ids, start, stop):
        if not self.env.user.has_group("project.group_project_user"):
            return {}
        if field == 'user_ids':
            start, stop = utc.localize(start), utc.localize(stop)
            return dict(
                self._gantt_progress_bar_user_ids(res_ids, start, stop),
                warning=_("This user isn't expected to have any tasks assigned during this period because they don't have any running contract."),
            )
        raise NotImplementedError(_("This Progress Bar is not implemented."))

    def _prepare_domains_for_all_deadlines(self, date_start, date_end):
        return {
            'project': [
                ('date', '>=', date_start),
                ('date_start', '<=', date_end),
            ],
            'milestone': [
                ('deadline', '>=', date_start),
                ('deadline', '<=', date_end),
                ('project_allow_milestones', '=', True),
            ],
        }

    @api.model
    @api.readonly
    def get_all_deadlines(self, date_start, date_end):
        """ Get all deadlines (milestones and projects) between date_start and date_end.

            :param date_start: The start date.
            :param date_end: The end date.

            :return: A dictionary with the field_name of tasks as key and list of records.
        """
        results = {}
        project_id = self.env.context.get('default_project_id', False)
        # get domains
        result_domains = self._prepare_domains_for_all_deadlines(date_start, date_end)
        project_domain = Domain(result_domains['project'])
        milestone_domain = Domain(result_domains['milestone'])

        if project_id:
            project_domain &= Domain('id', '=', project_id)
            milestone_domain &= Domain('project_id', '=', project_id)
        results['project_id'] = self.env['project.project'].search_read(
            project_domain,
            ['id', 'name', 'date', 'date_start']
        )
        results['milestone_id'] = self.env['project.milestone'].search_read(
            milestone_domain,
            ['name', 'deadline', 'is_deadline_exceeded', 'is_reached', 'project_id'],
        )
        return results

    def _get_template_default_context_whitelist(self):
        return [
            *super()._get_template_default_context_whitelist(),
            "planned_date_begin",
            "date_deadline",
        ]
