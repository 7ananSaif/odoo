# Part of Odoo. See LICENSE file for full copyright and licensing details.
import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, time, timedelta
from math import modf
from random import shuffle

import pytz
from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Datetime, Domain
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, SQL, float_utils, format_datetime, get_lang, babel_locale_parse, format_time, format_date
from odoo.tools.date_utils import get_timedelta, sum_intervals, weeknumber, weekstart, weekend
from odoo.tools.intervals import Intervals


def days_span(start_datetime, end_datetime):
    if not isinstance(start_datetime, datetime):
        raise TypeError
    if not isinstance(end_datetime, datetime):
        raise TypeError
    end = datetime.combine(end_datetime, datetime.min.time())
    start = datetime.combine(start_datetime, datetime.min.time())
    duration = end - start
    return duration.days + 1


class PlanningSlot(models.Model):
    _name = 'planning.slot'
    _description = 'Planning Shift'
    _order = 'start_datetime desc, id desc'
    _rec_name = 'name'
    _check_company_auto = True

    def _default_start_datetime(self):
        return datetime.combine(fields.Date.context_today(self), time.min)

    def _default_end_datetime(self):
        return datetime.combine(fields.Date.context_today(self), time.max)

    name = fields.Text('Note')
    resource_id = fields.Many2one('resource.resource', 'Resource', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", group_expand='_group_expand_resource_id')
    resource_type = fields.Selection(related='resource_id.resource_type')
    resource_color = fields.Integer(related='resource_id.color', string="Resource color")
    resource_roles = fields.Many2many(related='resource_id.role_ids')
    employee_id = fields.Many2one('hr.employee', 'Employee', compute='_compute_employee_id', store=True)
    work_email = fields.Char("Work Email", related='employee_id.work_email')
    work_location_id = fields.Many2one(related='employee_id.work_location_id')
    department_id = fields.Many2one(related='employee_id.department_id', store=True)
    user_id = fields.Many2one('res.users', string="User", related='resource_id.user_id', store=True, readonly=True)
    manager_id = fields.Many2one(related='employee_id.parent_id', store=True)
    job_title = fields.Char(related='employee_id.job_title')
    company_id = fields.Many2one('res.company', string="Company", required=True, compute="_compute_planning_slot_company_id", store=True, readonly=False)
    role_id = fields.Many2one('planning.role', string="Role", compute="_compute_role_id", store=True, readonly=False, copy=True, group_expand='_read_group_role_id',
        help="Define the roles your resources will perform (e.g. Chef, Bartender, Waiter). Create open shifts based on the roles needed for a mission, then assign those shifts to available resources.")
    color = fields.Integer("Color", compute='_compute_color')
    was_copied = fields.Boolean("This Shift Was Copied From Previous Week", default=False, readonly=True)
    access_token = fields.Char(default=lambda self: str(uuid.uuid4()), required=True, copy=False, readonly=True, export_string_translation=False)

    start_datetime = fields.Datetime(
        "Start Date", compute='_compute_datetime', store=True, readonly=False, required=True,
        copy=True)
    end_datetime = fields.Datetime(
        "End Date", compute='_compute_datetime', store=True, readonly=False, required=True,
        copy=True)
    # UI fields and warnings
    allow_self_unassign = fields.Boolean('Let Employee Unassign Themselves', compute='_compute_allow_self_unassign')
    self_unassign_days_before = fields.Integer(
        "Days before shift for unassignment",
        related="company_id.planning_self_unassign_days_before",
    )
    unassign_deadline = fields.Datetime('Deadline for unassignment', compute="_compute_unassign_deadline", export_string_translation=False)
    is_unassign_deadline_passed = fields.Boolean(compute="_compute_is_unassign_deadline_passed", export_string_translation=False)
    conflicting_slot_ids = fields.Many2many('planning.slot', compute='_compute_overlap_slot_count', export_string_translation=False)
    overlap_slot_count = fields.Integer(compute='_compute_overlap_slot_count', search='_search_overlap_slot_count', export_string_translation=False)
    is_past = fields.Boolean('Is This Shift In The Past?', compute='_compute_past_shift', export_string_translation=False)
    is_users_role = fields.Boolean('Is the shifts role one of the current user roles', compute='_compute_is_users_role', search='_search_is_users_role', export_string_translation=False)
    request_to_switch = fields.Boolean('Has there been a request to switch on this shift slot?', default=False, readonly=True, export_string_translation=False)

    # time allocation
    allocation_type = fields.Selection([
        ('planning', 'Planning'),
        ('forecast', 'Forecast'),
    ], compute='_compute_allocation_type')
    allocated_hours = fields.Float("Allocated Time", compute='_compute_allocated_hours', store=True, readonly=False)
    allocated_percentage = fields.Float("Allocated Time %", default=100,
        compute='_compute_allocated_percentage', store=True, readonly=False,
        aggregator="avg")
    duration = fields.Float("Duration", compute="_compute_slot_duration")

    # publication and sending
    publication_warning = fields.Boolean(
        "Modified Since Last Publication", default=False, compute='_compute_publication_warning',
        store=True, readonly=True, copy=False,
        help="If checked, it means that the shift contains has changed since its last publish.")
    state = fields.Selection([
            ('draft', 'Draft'),
            ('published', 'Published'),
    ], string='Status', default='draft')
    # template dummy fields (only for UI purpose)
    template_creation = fields.Boolean("Save as Template", store=False, inverse='_inverse_template_creation')
    template_autocomplete_ids = fields.Many2many('planning.slot.template', store=False, compute='_compute_template_autocomplete_ids', export_string_translation=False)
    template_id = fields.Many2one('planning.slot.template', string='Shift Templates', compute='_compute_template_id', readonly=False, store=True)
    template_reset = fields.Boolean(export_string_translation=False)
    previous_template_id = fields.Many2one('planning.slot.template', export_string_translation=False)
    allow_template_creation = fields.Boolean(string='Allow Template Creation', compute='_compute_allow_template_creation', export_string_translation=False)

    # Recurring (`repeat_` fields are none stored, only used for UI purpose)
    recurrency_id = fields.Many2one('planning.recurrency', readonly=True, index=True, ondelete="set null", copy=False, export_string_translation=False)
    repeat = fields.Boolean("Repeat", compute='_compute_repeat', inverse='_inverse_repeat',
        help="To avoid polluting your database and performance issues, shifts are only created for the next 6 months. They are then gradually created as time passes by in order to always get shifts 6 months ahead. This value can be modified from the settings of Planning, in debug mode.")
    repeat_interval = fields.Integer("Repeat every", default=1, compute='_compute_repeat_interval', inverse='_inverse_repeat')
    repeat_unit = fields.Selection([
        ('day', 'Days'),
        ('week', 'Weeks'),
        ('month', 'Months'),
        ('year', 'Years'),
    ], default='week', compute='_compute_repeat_unit', inverse='_inverse_repeat', required=True)
    repeat_type = fields.Selection([('forever', 'Forever'), ('until', 'Until'), ('x_times', 'Number of Occurrences')],
        string='Repeat Type', default='forever', compute='_compute_repeat_type', inverse='_inverse_repeat')
    repeat_until = fields.Date("Repeat Until", compute='_compute_repeat_until', inverse='_inverse_repeat')
    repeat_number = fields.Integer("Repetitions", default=1, compute='_compute_repeat_number', inverse='_inverse_repeat')
    recurrence_update = fields.Selection([
        ('this', 'This shift'),
        ('subsequent', 'This and following shifts'),
        ('all', 'All shifts'),
    ], default='this', store=False)
    confirm_delete = fields.Boolean(compute='_compute_confirm_delete', export_string_translation=False)

    is_hatched = fields.Boolean(compute='_compute_is_hatched', export_string_translation=False)

    slot_properties = fields.Properties('Properties', definition='role_id.slot_properties_definition', precompute=False)

    _check_start_date_lower_end_date = models.Constraint(
        'CHECK(end_datetime > start_datetime)',
        "The end date of a shift should be after its start date.",
    )
    _check_allocated_hours_positive = models.Constraint(
        'CHECK(allocated_hours >= 0)',
        "Allocated hours and allocated time percentage cannot be negative.",
    )

    @api.depends('role_id.color', 'resource_id.color')
    def _compute_color(self):
        for slot in self:
            slot.color = slot.role_id.color or slot.resource_id.color

    @api.depends('repeat_until')
    def _compute_confirm_delete(self):
        for slot in self:
            if slot.recurrency_id and slot.repeat_until:
                slot.confirm_delete = fields.Date.to_date(slot.recurrency_id.slot_ids.sorted('end_datetime')[-1].end_datetime) > slot.repeat_until
            else:
                slot.confirm_delete = False

    @api.constrains('repeat_until')
    def _check_repeat_until(self):
        if any(slot.repeat_until and slot.repeat_until < slot.start_datetime.date() for slot in self):
            raise UserError(self.env._(
                "Uh-oh! Let's keep things in the right order: the recurrence end date should always "
                "come after the shift start date. It's like trying to eat your breakfast before waking up - not possible!"
            ))

    @api.onchange('repeat_until')
    def _onchange_repeat_until(self):
        self._check_repeat_until()

    @api.depends('resource_id.company_id')
    def _compute_planning_slot_company_id(self):
        for slot in self:
            slot.company_id = slot.resource_id.company_id or slot.company_id or slot.env.company

    @api.depends('end_datetime')
    def _compute_past_shift(self):
        now = fields.Datetime.now()
        for slot in self:
            if slot.end_datetime:
                if slot.end_datetime < now:
                    slot.is_past = True
                else:
                    slot.is_past = False
            else:
                slot.is_past = False

    @api.depends('resource_id.employee_id', 'resource_type')
    def _compute_employee_id(self):
        for slot in self:
            slot.employee_id = slot.resource_id.with_context(active_test=False).employee_id if slot.resource_type == 'user' else False

    @api.depends('employee_id', 'template_id')
    def _compute_role_id(self):
        for slot in self:
            if not slot.role_id:
                slot.role_id = slot.resource_id.default_role_id

            if slot.template_id:
                slot.previous_template_id = slot.template_id
                if slot.template_id.role_id:
                    slot.role_id = slot.template_id.role_id
            elif slot.previous_template_id and not slot.template_id and slot.previous_template_id.role_id == slot.role_id:
                slot.role_id = False

    @api.depends('state')
    def _compute_is_hatched(self):
        for slot in self:
            slot.is_hatched = slot.state == 'draft'

    @api.depends('role_id')
    def _compute_is_users_role(self):
        user_resource_roles = self.env['resource.resource'].search([('user_id', '=', self.env.user.id)]).role_ids
        for slot in self:
            slot.is_users_role = (slot.role_id in user_resource_roles) or not user_resource_roles or not slot.role_id

    def _search_is_users_role(self, operator, value):
        if operator != 'in':
            return NotImplemented
        user_resource_roles = self.env['resource.resource'].search([('user_id', '=', self.env.user.id)]).role_ids
        if not user_resource_roles:
            return [(1, '=', 1)]
        return ['|', ('role_id', 'in', user_resource_roles.ids), ('role_id', '=', False)]

    @api.depends('start_datetime', 'end_datetime')
    def _compute_allocation_type(self):
        for slot in self:
            if slot.start_datetime and slot.end_datetime and slot._get_slot_duration() < 24:
                slot.allocation_type = 'planning'
            else:
                slot.allocation_type = 'forecast'

    @api.depends('allocated_hours')
    def _compute_allocated_percentage(self):
        # [TW:Cyclic dependency] allocated_hours,allocated_percentage
        # As allocated_hours and allocated percentage have some common dependencies, and are dependant one from another, we have to make sure
        # they are computed in the right order to get rid of undeterministic computation.
        #
        # Allocated percentage must only be recomputed if allocated_hours has been modified by the user and not in any other cases.
        # If allocated hours have to be recomputed, the allocated percentage have to keep its current value.
        # Hence, we stop the computation of allocated percentage if allocated hours have to be recomputed.
        allocated_hours_field = self._fields['allocated_hours']
        slots = self.filtered(lambda slot: not self.env.is_to_compute(allocated_hours_field, slot) and slot.start_datetime and slot.end_datetime and slot.start_datetime != slot.end_datetime)
        if not slots:
            return
        # if there are at least one slot having start or end date, call the _get_valid_work_intervals
        start_utc = pytz.utc.localize(min(slots.mapped('start_datetime')))
        end_utc = pytz.utc.localize(max(slots.mapped('end_datetime')))
        resources = slots.resource_id
        flexible_resources = resources.filtered(lambda r: r._is_flexible())
        regular_resources = resources - flexible_resources

        resource_work_intervals, calendar_work_intervals = regular_resources._get_valid_work_intervals(start_utc, end_utc, calendars=slots.company_id.resource_calendar_id)
        flexible_resources_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week = flexible_resources._get_flexible_resource_valid_work_intervals(start_utc, end_utc)
        resource_work_intervals.update(flexible_resources_work_intervals)

        for slot in slots:
            if not slot.resource_id and slot.allocation_type == 'planning':
                duration = slot._calculate_slot_duration()
                slot.allocated_percentage = 100 * slot.allocated_hours / duration if duration else 100
            else:
                work_hours = slot._get_working_hours_over_period(start_utc, end_utc, resource_work_intervals, calendar_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week)
                slot.allocated_percentage = 100 * slot.allocated_hours / work_hours if work_hours else 100

    @api.depends(
        'start_datetime', 'end_datetime', 'resource_id.calendar_id.flexible_hours',
        'company_id.resource_calendar_id', 'allocated_percentage')
    def _compute_allocated_hours(self):
        percentage_field = self._fields['allocated_percentage']
        self.env.remove_to_compute(percentage_field, self)
        open_slots = self.filtered(
            lambda s: (s.allocation_type == 'planning' or not s.company_id) and not s.resource_id
        )
        assigned_slots = self - open_slots
        for slot in open_slots:
            # for each planning slot, compute the duration
            ratio = slot.allocated_percentage / 100.0
            slot.allocated_hours = slot._calculate_slot_duration() * ratio
        if assigned_slots:
            # for forecasted slots, compute the conjunction of the slot resource's work intervals and the slot.
            unplanned_assigned_slots = assigned_slots.filtered_domain([
                '|', ('start_datetime', "=", False), ('end_datetime', "=", False),
            ])
            # Unplanned slots will have allocated hours set to 0.0 as there are no enough information
            # to compute the allocated hours (start or end datetime are mandatory for this computation)
            for slot in unplanned_assigned_slots:
                slot.allocated_hours = 0.0
            planned_assigned_slots = assigned_slots - unplanned_assigned_slots
            if not planned_assigned_slots:
                return
            # if there are at least one slot having start or end date, call the _get_valid_work_intervals
            start_utc = pytz.utc.localize(min(planned_assigned_slots.mapped('start_datetime')))
            end_utc = pytz.utc.localize(max(planned_assigned_slots.mapped('end_datetime')))

            resources = assigned_slots.resource_id
            flexible_resources = resources.filtered(lambda r: r._is_flexible())
            regular_resources = resources - flexible_resources

            # work intervals per resource are retrieved with a batch
            resource_work_intervals, calendar_work_intervals = regular_resources._get_valid_work_intervals(
                start_utc, end_utc, calendars=assigned_slots.company_id.resource_calendar_id
            )

            flexible_resources_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week = flexible_resources._get_flexible_resource_valid_work_intervals(start_utc, end_utc)
            resource_work_intervals.update(flexible_resources_work_intervals)

            slots_by_allocated_hours = defaultdict(lambda: self.env['planning.slot'])
            for slot in planned_assigned_slots:
                allocated_hour = slot._get_duration_over_period(
                    pytz.utc.localize(slot.start_datetime), pytz.utc.localize(slot.end_datetime),
                    resource_work_intervals, calendar_work_intervals,
                    flexible_resources_hours_per_day, flexible_resources_hours_per_week,
                    has_allocated_hours=False,
                )
                slots_by_allocated_hours[allocated_hour] |= slot
            for allocated_hours, slots in slots_by_allocated_hours.items():
                slots.allocated_hours = allocated_hours

    @api.depends('start_datetime', 'end_datetime', 'resource_id')
    def _compute_overlap_slot_count(self):
        if all(self._ids):
            self.flush_model(['start_datetime', 'end_datetime', 'resource_id'])
            query = """
                SELECT S1.id,ARRAY_AGG(DISTINCT S2.id) as conflict_ids FROM
                    planning_slot S1, planning_slot S2
                WHERE
                    S1.start_datetime < S2.end_datetime
                    AND S1.end_datetime > S2.start_datetime
                    AND S1.id <> S2.id AND S1.resource_id = S2.resource_id
                    AND S1.allocated_percentage + S2.allocated_percentage > 100
                    and S1.id in %s
                    AND (%s or S2.state = 'published')
                GROUP BY S1.id;
            """
            self.env.cr.execute(query, (tuple(self.ids), self.env.user.has_group('planning.group_planning_manager')))
            overlap_mapping = dict(self.env.cr.fetchall())
            for slot in self:
                slot_result = overlap_mapping.get(slot.id, [])
                slot.overlap_slot_count = len(slot_result)
                slot.conflicting_slot_ids = [(6, 0, slot_result)]
        else:
            # Allow fetching overlap without id if there is only one record
            # This is to allow displaying the warning when creating a new record without having an ID yet
            if len(self) == 1 and self.employee_id and self.start_datetime and self.end_datetime:
                query = """
                    SELECT ARRAY_AGG(s.id) as conflict_ids
                      FROM planning_slot s
                     WHERE s.employee_id = %s
                       AND s.start_datetime < %s
                       AND s.end_datetime > %s
                       AND s.allocated_percentage + %s > 100
                """
                self.env.cr.execute(query, (self.employee_id.id, self.end_datetime,
                                            self.start_datetime, self.allocated_percentage))
                overlaps = self.env.cr.dictfetchall()
                conflict_slot_ids = overlaps[0]['conflict_ids']
                if conflict_slot_ids:
                    if self._origin:
                        conflict_slot_ids = [slot_id for slot_id in conflict_slot_ids if slot_id != self._origin.id]
                    self.overlap_slot_count = len(conflict_slot_ids)
                    self.conflicting_slot_ids = [(6, 0, conflict_slot_ids)]
                else:
                    self.overlap_slot_count = False
                    self.conflicting_slot_ids = False
            else:
                self.overlap_slot_count = False
                self.conflicting_slot_ids = False

    @api.model
    def _search_overlap_slot_count(self, operator, value):
        if operator == 'in':
            return Domain.OR(self._search_overlap_slot_count('=', v) for v in value)
        if operator not in ['=', '>'] or not isinstance(value, int) or value != 0:
            raise NotImplementedError(self.env._('Operation not supported, you should always compare overlap_slot_count to 0 value with = or > operator.'))

        sql = SQL("""(
            SELECT S1.id
            FROM planning_slot S1
            WHERE EXISTS (
                SELECT 1
                  FROM planning_slot S2
                 WHERE S1.id <> S2.id
                   AND S1.resource_id = S2.resource_id
                   AND S1.start_datetime < S2.end_datetime
                   AND S1.end_datetime > S2.start_datetime
                   AND S1.allocated_percentage + S2.allocated_percentage > 100
            )
        )""")
        operator_new = "in" if operator == ">" else "not in"
        return [('id', operator_new, sql)]

    @api.depends('start_datetime', 'end_datetime')
    def _compute_slot_duration(self):
        for slot in self:
            slot.duration = slot._get_slot_duration()

    def _get_slot_duration(self):
        """Return the slot (effective) duration expressed in hours.
        """
        self.ensure_one()
        resource = self.resource_id
        if not self.start_datetime or not self.end_datetime:
            return False

        if resource:
            start = pytz.utc.localize(self.start_datetime).astimezone(pytz.timezone(resource.tz))
            end = pytz.utc.localize(self.end_datetime).astimezone(pytz.timezone(resource.tz))
            if resource._is_flexible():
                work_intervals, hours_per_day, hours_per_week = self.resource_id._get_flexible_resource_valid_work_intervals(start, end)
                return self.resource_id._get_flexible_resource_work_hours(work_intervals[self.resource_id.id], hours_per_day[self.resource_id.id], hours_per_week[self.resource_id.id])
            else:
                work_intervals, _dummy = resource._get_valid_work_intervals(start, end)
                return sum_intervals(work_intervals[resource.id])
        return (self.end_datetime - self.start_datetime).total_seconds() / 3600.0

    def _get_domain_template_slots(self):
        domain = []
        roles = self.resource_id.role_ids
        if self.role_id:
            roles |= self.role_id
        if roles:
            domain += ['|', ('role_id', 'in', roles.ids), ('role_id', '=', False)]
        return domain

    @api.depends('role_id', 'employee_id')
    def _compute_template_autocomplete_ids(self):
        for slot in self:
            domain = slot._get_domain_template_slots()
            templates = self.env['planning.slot.template'].search(domain, order='start_time', limit=10)
            slot.template_autocomplete_ids = templates + slot.template_id

    @api.depends('employee_id', 'role_id', 'start_datetime', 'end_datetime')
    def _compute_template_id(self):
        for slot in self.filtered(lambda s: s.template_id):
            slot.previous_template_id = slot.template_id
            slot.template_reset = False
            if slot._different_than_template():
                slot.template_id = False
                slot.previous_template_id = False
                slot.template_reset = True

    def _different_than_template(self, check_empty=True):
        self.ensure_one()
        if not (self.start_datetime and self.end_datetime):
            return True
        template_fields = self._get_template_fields().items()
        for template_field, slot_field in template_fields:
            if self.template_id[template_field] or not check_empty:
                if template_field in ('start_time', 'end_time'):
                    h = int(self.template_id[template_field])
                    m = round(modf(self.template_id[template_field])[0] * 60.0)
                    slot_time = self[slot_field].astimezone(pytz.timezone(self._get_tz()))
                    if slot_time.hour != h or slot_time.minute != m:
                        return True
                elif template_field == 'duration_days':
                    if self.start_datetime and self.end_datetime and \
                            days_span(self.start_datetime, self.end_datetime) != self.template_id[template_field]:
                        return True
                elif self[slot_field] != self.template_id[template_field]:
                    return True

        return False

    @api.depends('template_id', 'role_id', 'allocated_hours', 'start_datetime', 'end_datetime')
    def _compute_allow_template_creation(self):
        for slot in self:
            if not (slot.start_datetime and slot.end_datetime):
                slot.allow_template_creation = False
                continue

            values = slot._prepare_template_values()
            domain = [(x, '=', values[x]) for x in values]
            existing_templates = self.env['planning.slot.template'].search(domain, limit=1)
            slot.allow_template_creation = not existing_templates and slot._different_than_template(check_empty=False)

    @api.depends('recurrency_id')
    def _compute_repeat(self):
        for slot in self:
            if slot.recurrency_id:
                slot.repeat = True
            else:
                slot.repeat = False

    @api.depends('recurrency_id.repeat_interval')
    def _compute_repeat_interval(self):
        recurrency_slots = self.filtered('recurrency_id')
        for slot in recurrency_slots:
            if slot.recurrency_id:
                slot.repeat_interval = slot.recurrency_id.repeat_interval
        (self - recurrency_slots).update(self.default_get(['repeat_interval']))

    @api.depends('recurrency_id.repeat_until', 'repeat', 'repeat_type')
    def _compute_repeat_until(self):
        for slot in self:
            repeat_until = False
            if slot.repeat and slot.repeat_type == 'until':
                if slot.recurrency_id and slot.recurrency_id.repeat_until:
                    repeat_until = slot.recurrency_id.repeat_until
                elif slot.start_datetime:
                    repeat_until = slot.start_datetime + relativedelta(weeks=1)
            slot.repeat_until = repeat_until

    @api.depends('recurrency_id.repeat_number', 'repeat_type')
    def _compute_repeat_number(self):
        recurrency_slots = self.filtered('recurrency_id')
        for slot in recurrency_slots:
            slot.repeat_number = slot.recurrency_id.repeat_number
        (self - recurrency_slots).update(self.default_get(['repeat_number']))

    @api.depends('recurrency_id.repeat_unit')
    def _compute_repeat_unit(self):
        non_recurrent_slots = self.env['planning.slot']
        for slot in self:
            if slot.recurrency_id:
                slot.repeat_unit = slot.recurrency_id.repeat_unit
            else:
                non_recurrent_slots += slot
        non_recurrent_slots.update(self.default_get(['repeat_unit']))

    @api.depends('recurrency_id.repeat_type')
    def _compute_repeat_type(self):
        recurrency_slots = self.filtered('recurrency_id')
        for slot in recurrency_slots:
            if slot.recurrency_id:
                slot.repeat_type = slot.recurrency_id.repeat_type
        (self - recurrency_slots).update(self.default_get(['repeat_type']))

    def _inverse_repeat(self):
        for slot in self:
            if slot.repeat and not slot.recurrency_id.id:  # create the recurrence
                repeat_until = False
                repeat_number = 0
                if slot.repeat_type == "until":
                    repeat_until = datetime.combine(fields.Date.to_date(slot.repeat_until), datetime.max.time())
                    repeat_until = repeat_until.replace(tzinfo=pytz.timezone(slot.company_id.resource_calendar_id.tz or 'UTC')).astimezone(pytz.utc).replace(tzinfo=None)
                if slot.repeat_type == 'x_times':
                    repeat_number = slot.repeat_number
                recurrency_values = {
                    'repeat_interval': slot.repeat_interval,
                    'repeat_unit': slot.repeat_unit,
                    'repeat_until': repeat_until,
                    'repeat_number': repeat_number,
                    'repeat_type': slot.repeat_type,
                    'company_id': slot.company_id.id,
                }
                recurrence = self.env['planning.recurrency'].create(recurrency_values)
                slot.recurrency_id = recurrence
                slot.recurrency_id._repeat_slot()
            # user wants to delete the recurrence
            # here we also check that we don't delete by mistake a slot of which the repeat parameters have been changed
            elif not slot.repeat and slot.recurrency_id.id:
                slot.recurrency_id._delete_slot(slot.end_datetime)
                slot.recurrency_id.unlink()  # will set recurrency_id to NULL

    def _inverse_template_creation(self):
        PlanningTemplate = self.env['planning.slot.template']
        for slot in self.filtered(lambda s: s.template_creation):
            values = slot._prepare_template_values()
            domain = [(x, '=', values[x]) for x in values]
            existing_templates = PlanningTemplate.search(domain, limit=1)
            if not existing_templates:
                template = PlanningTemplate.create(values)
                slot.write({'template_id': template.id, 'previous_template_id': template.id})
            else:
                slot.write({'template_id': existing_templates.id})

    def _get_non_working_days_bounds(self, start_datetime, end_datetime, resource=False):
        resource = resource or self.env.user.employee_id.resource_id
        user_tz = pytz.timezone(self.env.user.tz
            or (resource.employee_id and resource.employee_id.tz)
            or resource.tz
            or self.env.context.get('tz')
            or self.env.user.company_id.resource_calendar_id.tz
            or 'UTC'
        )
        start_date_in_user_tz = start_datetime.astimezone(user_tz)
        offset = start_date_in_user_tz.utcoffset().total_seconds() / 3600
        return (
            (start_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None) + timedelta(hours=8 - offset)),
            (end_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None) + timedelta(hours=17 - offset))
        )

    @api.model
    def _calculate_start_end_dates(self,
                                 start_datetime,
                                 end_datetime,
                                 resource_id,
                                 template_id,
                                 previous_template_id,
                                 template_reset):
        """
        Calculate the start and end dates for a given planning slot based on various parameters.

        Returns: A tuple containing the calculated start and end datetime values in UTC without timezone.
        """
        def convert_datetime_timezone(dt, tz):
            return dt and pytz.utc.localize(dt).astimezone(tz)

        resource = resource_id or self.env.user.employee_id.resource_id
        company = self.company_id or self.env.company
        employee = resource_id.employee_id if resource_id.resource_type == 'user' else False
        user_tz = pytz.timezone(self.env.user.tz
                                or (employee and employee.tz)
                                or resource_id.tz
                                or self.env.context.get('tz')
                                or self.env.user.company_id.resource_calendar_id.tz
                                or 'UTC')

        # start_datetime and end_datetime are from 00:00 to 23:59 in user timezone
        # Converted in UTC, it gives an offset for any other timezone, _convert_datetime_timezone removes the offset
        # If start_datetime and end_datetime are None, the resource should follow the company's working calendar and return the work intervals based on the time zone and the company's working calendar.
        intervals = []
        start = convert_datetime_timezone(start_datetime, user_tz) if start_datetime else user_tz.localize(self._default_start_datetime())
        end = convert_datetime_timezone(end_datetime, user_tz) if end_datetime else user_tz.localize(self._default_end_datetime())

        if not template_id:
            # Transform the current column's start/end_datetime to the user's timezone from UTC
            # Look at the work intervals to examine whether the current start/end_datetimes are inside working hours
            calendar_id = resource.calendar_id or company.resource_calendar_id
            work_interval = calendar_id._work_intervals_batch(start, end)[False]
            intervals = [(date_start, date_stop) for date_start, date_stop, attendance in work_interval]
            if not intervals and not self.env.context.get('planning_keep_default_datetime', False):
                # If we are outside working hours, we do not edit the start/end_datetime
                # Return the start/end times back at UTC and remove the tzinfo from the object
                return self._get_non_working_days_bounds(start, end, resource)

        # start_datetime and end_datetime are from 00:00 to 23:59 in user timezone
        # Converted in UTC, it gives an offset for any other timezone, _convert_datetime_timezone removes the offset
        start = convert_datetime_timezone(start_datetime, user_tz) if start_datetime else user_tz.localize(self._default_start_datetime())
        end = convert_datetime_timezone(end_datetime, user_tz) if end_datetime else user_tz.localize(self._default_end_datetime())

        # Get start and end in resource timezone so that it begins/ends at the same hour of the day as it would be in the user timezone
        # This is needed because _adjust_to_calendar takes start as datetime for the start of the day and end as end time for the end of the day
        # This can lead to different results depending on the timezone difference between the current user and the resource.
        # Example:
        # The user is in Europe/Brussels timezone (CET, UTC+1)
        # The resource is Asia/Krasnoyarsk timezone (IST, UTC+7)
        # The resource has two shifts during the day:
        #       - Morning shift: 8 to 12
        #       - Afternoon shift: 13 to 17
        # When the user selects a day to plan a shift for the resource, he expects to have the shift scheduled according to the resource's calendar given a search range between 00:00 and 23:59
        # The datetime received from the frontend is in the user's timezone meaning that the search interval will be between 23:00 and 22:59 in UTC
        # If the datetime is not adjusted to the resource's calendar beforehand, _adjust_to_calendar and _get_closest_work_time will shift the time to the resource's timezone.
        # The datetime given to _get_closest_work_time will be 6 AM once shifted in the resource's timezone. This will properly find the start of the morning shift at 8AM
        # For the afternoon shift, _get_closest_work_time will search the end of the shift that is close to 6AM the day after.
        # The closest shift found based on the end datetime will be the morning shift meaning that the work_interval_end will be the end of the morning shift the following day.
        # Determine the start and end dates from _work_intervals_batch and convert them to the resource's time zone.
        if resource and intervals:
            start = pytz.timezone(resource.tz).localize(intervals[0][0].replace(tzinfo=None))
            end = pytz.timezone(resource.tz).localize(intervals[-1][-1].replace(tzinfo=None))

        if not previous_template_id and not template_reset:
            start = start.astimezone(pytz.utc).replace(tzinfo=None)
            end = end.astimezone(pytz.utc).replace(tzinfo=None)

        if template_id and start_datetime:
            h = int(template_id.start_time)
            m = round(modf(template_id.start_time)[0] * 60.0)
            start = pytz.utc.localize(start_datetime).astimezone(pytz.timezone(resource.tz) if
                                                                 resource else user_tz)
            start = start.replace(hour=int(h), minute=int(m))

            h = int(template_id.end_time)
            m = round(modf(template_id.end_time)[0] * 60.0)
            end = (start + relativedelta(days=(template_id.duration_days - 1), hour=0, minute=0, second=0))
            if template_id.duration_days > 1 and resource_id.calendar_id:
                end = resource.calendar_id.plan_days(template_id.duration_days, start, compute_leaves=True)
            end = end.replace(hour=int(h), minute=int(m))

            if resource and not resource._is_flexible():
                work_interval, _dummy = resource._get_valid_work_intervals(
                    start,
                    end
                )
                start = start.astimezone(pytz.utc).replace(tzinfo=None)
                end = work_interval[resource.id]._items[-1][1].astimezone(pytz.utc).replace(tzinfo=None) \
                    if work_interval[resource.id]._items \
                    else end

        # Need to remove the tzinfo in start and end as without these it leads to a traceback
        # when the start time is empty
        start = start.astimezone(pytz.utc).replace(tzinfo=None) if start.tzinfo else start
        end = end.astimezone(pytz.utc).replace(tzinfo=None) if end.tzinfo else end
        return (start, end)

    @api.depends('template_id')
    def _compute_datetime(self):
        for slot in self.filtered(lambda s: s.template_id):
            slot.start_datetime, slot.end_datetime = self._calculate_start_end_dates(slot.start_datetime,
                                                                                     slot.end_datetime,
                                                                                     slot.resource_id,
                                                                                     slot.template_id,
                                                                                     slot.previous_template_id,
                                                                                     slot.template_reset)

    @api.depends(lambda self: self._get_fields_breaking_publication())
    def _compute_publication_warning(self):
        for slot in self:
            slot.publication_warning = slot.resource_id and slot.resource_type != 'material' and slot.state == 'published'

    def _company_working_hours(self, start, end):
        company = self.company_id or self.env.company
        work_interval = company.resource_calendar_id._work_intervals_batch(start, end)[False]
        intervals = [(date_start, date_stop) for date_start, date_stop, attendance in work_interval]

        if not intervals:
            return ()

        start_datetime, end_datetime = (start, end)
        if intervals and (end_datetime - start_datetime).days == 0:  # Then we want the first working day and keep the end hours of this day
            start_datetime = intervals[0][0]
            end_datetime = [stop for start, stop in intervals if stop.date() == start_datetime.date()][-1]
        elif intervals and (end_datetime - start_datetime).days > 0:
            start_datetime = intervals[0][0]
            end_datetime = intervals[-1][1]

        return (start_datetime, end_datetime)

    def _compute_allow_self_unassign(self):
        allow_self_unassign_planning = self.filtered(lambda p: p.company_id.planning_employee_unavailabilities == 'unassign')
        allow_self_unassign_planning.allow_self_unassign = True
        (self - allow_self_unassign_planning).allow_self_unassign = False

    @api.depends('self_unassign_days_before', 'start_datetime')
    def _compute_unassign_deadline(self):
        slots_with_date = self.filtered('start_datetime')
        (self - slots_with_date).unassign_deadline = False
        for slot in slots_with_date:
            slot.unassign_deadline = fields.Datetime.subtract(slot.start_datetime, days=slot.self_unassign_days_before)

    @api.depends('unassign_deadline')
    def _compute_is_unassign_deadline_passed(self):
        slots_with_date = self.filtered('unassign_deadline')
        (self - slots_with_date).is_unassign_deadline_passed = False
        for slot in slots_with_date:
            slot.is_unassign_deadline_passed = slot.unassign_deadline < fields.Datetime.now()

    # ----------------------------------------------------
    # ORM overrides
    # ----------------------------------------------------

    @api.model
    def _read_group_fields_nullify(self):
        return []

    @api.model
    def formatted_read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[dict]:
        res = super().formatted_read_group(domain, groupby, aggregates, having, offset, limit, order)
        for aggregate_nullify in self._read_group_fields_nullify():
            if aggregate_nullify not in aggregates:
                continue
            for row in res:
                if row[aggregate_nullify] == 0:
                    row[aggregate_nullify] = False
        return res

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        if res.get('resource_id'):
            resource_id = self.env['resource.resource'].browse(res.get('resource_id'))
            template_id, previous_template_id = [res.get(key) for key in ['template_id', 'previous_template_id']]
            template_id = template_id and self.env['planning.slot.template'].browse(template_id)
            previous_template_id = template_id and self.env['planning.slot.template'].browse(previous_template_id)
            res['start_datetime'], res['end_datetime'] = self._calculate_start_end_dates(res.get('start_datetime'),
                                                                                       res.get('end_datetime'),
                                                                                       resource_id,
                                                                                       template_id,
                                                                                       previous_template_id,
                                                                                       res.get('template_reset'))
        else:
            if 'start_datetime' in fields and not self.env.context.get('planning_keep_default_datetime', False):
                start_datetime = Datetime.to_datetime(res.get('start_datetime')) if res.get('start_datetime') else self._default_start_datetime()
                end_datetime = Datetime.to_datetime(res.get('end_datetime')) if res.get('end_datetime') else self._default_end_datetime()
                start = pytz.utc.localize(start_datetime)
                end = pytz.utc.localize(end_datetime) if end_datetime else self._default_end_datetime()
                opening_hours = self._company_working_hours(start, end)
                if opening_hours:
                    res['start_datetime'] = opening_hours[0].astimezone(pytz.utc).replace(tzinfo=None)
                    if 'end_datetime' in fields:
                        res['end_datetime'] = opening_hours[1].astimezone(pytz.utc).replace(tzinfo=None)
                else:
                    res['start_datetime'], end_datetime = self._get_non_working_days_bounds(start_datetime, end_datetime)
                    if 'end_datetime' in fields:
                        res['end_datetime'] = end_datetime

        return res

    def _init_column(self, column_name):
        """ Initialize the value of the given column for existing rows.
            Overridden here because we need to generate different access tokens
            and by default _init_column calls the default method once and applies
            it for every record.
        """
        if column_name != 'access_token':
            super()._init_column(column_name)
        else:
            query = """
                UPDATE %(table_name)s
                SET access_token = md5(md5(random()::varchar || id::varchar) || clock_timestamp()::varchar)::uuid::varchar
                WHERE access_token IS NULL
            """ % {'table_name': self._table}
            self.env.cr.execute(query)

    @api.depends(lambda self: self._display_name_fields())
    @api.depends_context('group_by')
    def _compute_display_name(self):
        group_by = self.env.context.get('group_by', [])
        field_list = [fname for fname in self._display_name_fields() if fname not in group_by]

        # Sudo as a planning manager is not able to read private project if he is not project manager.
        self = self.sudo()  # noqa: PLW0642
        for slot in self.with_context(hide_partner_ref=True):
            # label part, depending on context `groupby`
            name_values = [
                self._fields[fname].convert_to_display_name(slot[fname], slot) if fname != 'resource_id' else slot.resource_id.name
                for fname in field_list
                if slot[fname] and not (fname == 'resource_id' and slot.resource_type != 'material')
            ][:4]  # limit to 4 labels
            name = ' - '.join(name_values)

            # add unicode bubble to tell there is a note
            if slot.name:
                name = f'{name} \U0001F4AC'

            slot.display_name = name or ''

    @api.model_create_multi
    def create(self, vals_list):
        Resource = self.env['resource.resource']
        for vals in vals_list:
            if vals.get('resource_id'):
                resource = Resource.browse(vals.get('resource_id'))
                if not vals.get('company_id'):
                    vals['company_id'] = resource.company_id.id
                if resource.resource_type == 'material':
                    vals['state'] = 'published'
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id
        if self.env.context.get("multi_create"):
            vals_list_updated = []
            resource_per_id = {}
            user_tz = pytz.timezone(self._get_tz())
            min_datetime = fields.Datetime.from_string(vals_list[0]['start_datetime']).astimezone(user_tz)
            max_datetime = fields.Datetime.from_string(vals_list[-1]['end_datetime']).astimezone(user_tz)
            for vals in vals_list:
                if resource_id := vals.get('resource_id'):
                    resource = resource_per_id.get(resource_id)
                    if not resource:
                        resource = Resource.browse(resource_id)
                        resource_per_id[resource_id] = resource
                        Resource |= resource
            schedule, _ = Resource._get_valid_work_intervals(min_datetime, max_datetime)
            for vals in vals_list:
                if resource_id := vals.get('resource_id'):
                    shift_interval = Intervals([(
                        fields.Datetime.from_string(vals.get('start_datetime')).astimezone(user_tz),
                        fields.Datetime.from_string(vals.get('end_datetime')).astimezone(user_tz),
                        self.env['resource.calendar.attendance'],
                    )])
                    if shift_interval & schedule[resource_id]:
                        vals_list_updated.append(vals)
            if vals_list_updated:
                vals_list = vals_list_updated
        return super().create(vals_list)

    def create_batch_from_calendar(self, vals_list):
        if not len(vals_list):
            return
        template_id = self.env['planning.slot.template'].browse(vals_list[0]['template_id'])

        resources = self.env['resource.resource']
        resource_per_id = {}
        min_datetime = datetime.strptime(vals_list[0]['start_datetime'], '%Y-%m-%d %H:%M:%S')
        max_datetime = datetime.strptime(vals_list[-1]['end_datetime'], '%Y-%m-%d %H:%M:%S')
        if template_id.duration_days > 1:
            max_datetime = max_datetime + relativedelta(months=2)

        for vals in vals_list:
            if resource_id := vals.get('resource_id'):
                resource = resource_per_id.get(resource_id)
                if not resource:
                    resource = resources.browse(resource_id)
                    resource_per_id[resource_id] = resource
                    resources |= resource

        user_tz = pytz.timezone(self._get_tz())
        schedule, _ = resources._get_valid_work_intervals(min_datetime.astimezone(user_tz),
                                                          max_datetime.astimezone(user_tz))
        vals_list_updated_slots = []
        if template_id.duration_days > 1:
            for vals in vals_list:
                if resource_id := vals.get('resource_id'):
                    end_datetime = datetime.strptime(vals['end_datetime'], '%Y-%m-%d %H:%M:%S')
                    current_end_datetime = end_datetime - relativedelta(days=template_id.duration_days)
                    current_start_datetime = datetime.strptime(vals['start_datetime'], '%Y-%m-%d %H:%M:%S') - relativedelta(days=1)
                    working_days_to_assign = template_id.duration_days
                    while working_days_to_assign > 0 and current_end_datetime < max_datetime:

                        current_start_datetime += relativedelta(days=1)
                        current_end_datetime += relativedelta(days=1)
                        shift_interval = Intervals([(
                            current_start_datetime.astimezone(user_tz),
                            current_end_datetime.astimezone(user_tz),
                            self.env['resource.calendar.attendance'],
                        )])
                        if shift_interval & schedule[resource_id]:
                            working_days_to_assign -= 1

                    vals['end_datetime'] = current_end_datetime.strftime('%Y-%m-%d %H:%M:%S')
                    vals_list_updated_slots.append(vals)
                else:
                    vals_list_updated_slots = vals_list
                    break
        else:
            for vals in vals_list:
                if resource_id := vals.get('resource_id'):
                    shift_interval = Intervals([(
                        datetime.strptime(vals['start_datetime'], '%Y-%m-%d %H:%M:%S').astimezone(user_tz),
                        datetime.strptime(vals['end_datetime'], '%Y-%m-%d %H:%M:%S').astimezone(user_tz),
                        self.env['resource.calendar.attendance'],
                    )])
                    if shift_interval & schedule[resource_id]:
                        vals_list_updated_slots.append(vals)
                else:
                    vals_list_updated_slots.append(vals)

        return self.create(vals_list_updated_slots)

    def write(self, vals):
        values = vals
        new_resource = self.env['resource.resource'].browse(values['resource_id']) if 'resource_id' in values else None
        if new_resource and new_resource.resource_type == 'material':
            values['state'] = 'published'
        # if the resource_id is changed while the shift has already been published and the resource is human, that means that the shift has been re-assigned
        # and thus we should send the email about the shift re-assignment
        for slot in self.filtered(lambda s: new_resource and s.state == 'published' and s.resource_type == 'user' and new_resource.resource_type == 'user'):
            self._send_shift_assigned(slot, new_resource)
        for slot in self:
            if slot.request_to_switch and (
                (new_resource and slot.resource_id != new_resource)
                or ('start_datetime' in values and slot.start_datetime != values['start_datetime'])
                or ('end_datetime' in values and slot.end_datetime != values['end_datetime'])
            ):
                values['request_to_switch'] = False

        recurrence_update = values.pop('recurrence_update', 'this')
        shifts_to_update = self
        # `self` has no recurrence when we just set it, in which case there's no other slot to update
        if shifts_to_update.recurrency_id and recurrence_update != 'this':
            # Updating "all" or "subsequent" slots is only possible on one record at a time
            shifts_to_update.ensure_one()
            datetime_keys = values.keys() & {'start_datetime', 'end_datetime'}
            if recurrence_update == 'subsequent':
                subsequent_slots = self.search([
                    '&',
                        ('recurrency_id', '=', shifts_to_update.recurrency_id.id),
                        ('start_datetime', '>', shifts_to_update.start_datetime),
                ])
                if datetime_keys:
                    values["repeat_type"] = self.repeat_type
                    values["repeat_number"] = 1 + len(subsequent_slots)
                    (shifts_to_update.recurrency_id.slot_ids - subsequent_slots - shifts_to_update).recurrency_id = False
                    subsequent_slots.unlink()
                else:
                    shifts_to_update |= subsequent_slots
            else:
                all_slots = shifts_to_update.recurrency_id.slot_ids.sorted('start_datetime')
                if datetime_keys:
                    first_slot = all_slots[0]
                    values.update({
                        datetime_key: fields.Datetime.from_string(values[datetime_key]) - (self[datetime_key] - first_slot[datetime_key])
                        for datetime_key in datetime_keys
                    })
                    values["repeat_type"] = first_slot.repeat_type    # this is to ensure that the subsequent slots are recreated
                    (all_slots - first_slot).unlink()
                    shifts_to_update = first_slot
                else:
                    shifts_to_update |= all_slots

        result = super(PlanningSlot, shifts_to_update).write(values)
        # recurrence
        if any(key in ('repeat', 'repeat_unit', 'repeat_type', 'repeat_until', 'repeat_interval', 'repeat_number') for key in values):
            # User is trying to change this record's recurrence so we delete future slots belonging to recurrence A
            # and we create recurrence B from now on w/ the new parameters
            for slot in shifts_to_update:
                recurrence = slot.recurrency_id
                if recurrence and values.get('repeat') is None:
                    repeat_type = values.get('repeat_type') or recurrence.repeat_type
                    repeat_until = values.get('repeat_until') or recurrence.repeat_until
                    repeat_number = values.get('repeat_number', 0) or slot.repeat_number
                    if repeat_type == 'until':
                        repeat_until = datetime.combine(fields.Date.to_date(repeat_until), datetime.max.time())
                        repeat_until = repeat_until.replace(tzinfo=pytz.timezone(slot.company_id.resource_calendar_id.tz or 'UTC')).astimezone(pytz.utc).replace(tzinfo=None)
                    recurrency_values = {
                        'repeat_interval': values.get('repeat_interval') or recurrence.repeat_interval,
                        'repeat_unit': values.get('repeat_unit') or recurrence.repeat_unit,
                        'repeat_until': repeat_until if repeat_type == 'until' else False,
                        'repeat_number': repeat_number,
                        'repeat_type': repeat_type,
                        'company_id': slot.company_id.id,
                    }
                    recurrence.write(recurrency_values)
                    if slot.repeat_type == 'x_times':
                        final_slot = min(repeat_number, len(recurrence.slot_ids))
                        recurrency_values['repeat_until'] = recurrence.slot_ids.sorted('end_datetime')[final_slot - 1].end_datetime
                    end_datetime = slot.end_datetime if values.get('repeat_unit') else recurrency_values.get('repeat_until')
                    recurrence._delete_slot(end_datetime)
                    recurrence._repeat_slot()
        return result

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        active_resources = self.env['resource.resource']
        planning_split_tool = self.env.context.get('planning_split_tool')
        check_resource_active = not ((default and 'resource_id' in default) or planning_split_tool)
        if check_resource_active:
            active_resources = self.resource_id.filtered('active')
        for planning, vals in zip(self, vals_list):
            if planning_split_tool:
                vals['state'] = planning.state
            if check_resource_active and planning.resource_id and planning.resource_id not in active_resources:
                vals['resource_id'] = False
        return vals_list

    def copy(self, default=None):
        result = super().copy(default=default)
        # force recompute of stored computed fields depending on start_datetime and resource_id
        if default and {'start_datetime', 'resource_id'} & default.keys():
            result._compute_allocated_hours()
        return result

    def split_pill(self, values):
        """
            Split the slot in two parts
            1. Copy the pill and modify the start time (second pill)
            2. Modify the original pill and modify the end time (first pill)

            values expected:
            :start_datetime: the start datetime of the second pill
            :end_datetime: the end datetime of the first pill
        """

        # Important Note: When you change this method logic, change it also in _split_fake_pill
        # in the same file, they should be identical
        result = self.copy({'start_datetime': values.get('start_datetime')})
        self.write({'end_datetime': values.get('end_datetime')})
        return result.id

    # ----------------------------------------------------
    # Actions
    # ----------------------------------------------------

    def action_address_recurrency(self, recurrence_update):
        """ :param recurrence_update: the occurences to be targetted (this, subsequent, all)
        """
        if recurrence_update == 'this':
            return
        domain = Domain('id', 'not in', self.ids)
        if recurrence_update == 'all':
            domain &= Domain('recurrency_id', 'in', self.recurrency_id.ids)
        elif recurrence_update == 'subsequent':
            start_date_per_recurrency_id = {}
            for shift in self:
                if shift.recurrency_id.id not in start_date_per_recurrency_id\
                    or shift.start_datetime < start_date_per_recurrency_id[shift.recurrency_id.id]:
                    start_date_per_recurrency_id[shift.recurrency_id.id] = shift.start_datetime
            domain &= Domain.OR(
                Domain('recurrency_id', '=', recurrency_id) & Domain('start_datetime', '>', start_datetime)
                for recurrency_id, start_datetime in start_date_per_recurrency_id.items()
            )
        sibling_slots = self.env['planning.slot'].search(domain)
        self.recurrency_id.unlink()
        sibling_slots.unlink()

    def action_unlink(self):
        self.unlink()
        return {'type': 'ir.actions.act_window_close'}

    def action_see_overlaping_slots(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'planning.slot',
            'name': self.env._('Shifts in Conflict'),
            'views': [[False, "gantt"], [False, "list"], [False, "form"]],
            'context': {
                'initialDate': min(self.mapped('start_datetime')),
                'search_default_conflict_shifts': True,
                'search_default_resource_id': self.resource_id.ids
            }
        }

    def action_self_assign(self):
        """ Allow planning user to self assign open shift. """
        self.ensure_one()
        # user must at least 'read' the shift to self assign (Prevent any user in the system (portal, ...) to assign themselves)
        if not self.has_access('read'):
            raise AccessError(self.env._("You don't have the right to assign yourself to shifts."))
        if self.resource_id and not self.request_to_switch:
            raise UserError(self.env._("You can not assign yourself to an already assigned shift."))
        if self.is_past:
            if self.request_to_switch:
                self.sudo().write({'request_to_switch': False})
            raise UserError(self.env._("You cannot assign yourself to a shift in the past."))
        if self.company_id in self.env.user.employee_ids.mapped('company_id'):
            resource_id = self.env.user.employee_ids.filtered(lambda e: e.company_id == self.company_id)[
                0].resource_id.id
        elif len(self.env.user.employee_ids) == 1:
            resource_id = self.env.user.employee_ids.resource_id.id
        else:
            raise UserError(self.env._("You cannot assign yourself to a shift belonging to another company."))
        return self.sudo().write({'resource_id': resource_id})

    def action_self_unassign(self):
        """ Allow planning user to self unassign from a shift, if the feature is activated """
        self.ensure_one()
        # The following condition will check the read access on planning.slot, and that user must at least 'read' the
        # shift to self unassign. Prevent any user in the system (portal, ...) to unassign any shift.
        if not self.allow_self_unassign:
            raise UserError(self.env._("The company does not allow you to unassign yourself from shifts."))
        if self.is_unassign_deadline_passed:
            raise UserError(self.env._("The deadline for unassignment has passed."))
        if self.employee_id not in self.env.user.employee_ids:
            raise UserError(self.env._("You can not unassign another employee than yourself."))
        if self.is_past:
            raise UserError(self.env._("You cannot unassign yourself from a shift in the past."))
        return self.sudo().write({'resource_id': False})

    def action_switch_shift(self):
        """ Allow planning user to make shift available for other people to assign themselves to. """
        self.ensure_one()
        # same as with self-assign, a user must be able to 'read' the shift in order to request a switch
        if not self.has_access('read'):
            raise AccessError(self.env._("You don't have the right to switch shifts."))
        if self.employee_id != self.env.user.employee_id:
            raise UserError(self.env._("You cannot request to switch a shift that is assigned to another user."))
        if self.is_past:
            raise UserError(self.env._("You cannot switch a shift that is in the past."))
        return self.sudo().write({'request_to_switch': True})

    def action_cancel_switch(self):
        """ Allows the planning user to cancel the shift switch if they change their mind at a later date """
        self.ensure_one()
        # same as above, the user rights are checked in order for the operation to be completed
        if not self.has_access('read'):
            raise AccessError(self.env._("You don't have the right to cancel a request to switch."))
        if self.employee_id != self.env.user.employee_id:
            raise UserError(self.env._("You cannot cancel a request to switch made by another user."))
        if self.is_past:
            raise UserError(self.env._("You cannot cancel a request to switch that is in the past."))
        return self.sudo().write({'request_to_switch': False})

    def _get_ics_file(self, calendar, employee_tz):
        def ics_datetime(idate):
            tz_info = employee_tz or self.env.user.tz or 'UTC'
            return idate and idate.astimezone(pytz.timezone(tz_info))

        for slot in self:
            event = calendar.add('vevent')
            if not slot.start_datetime or not slot.end_datetime:
                raise UserError(self.env._("First you have to specify the date of the invitation."))
            event.add('created').value = ics_datetime(fields.Datetime.now())
            event.add('dtstart').value = ics_datetime(slot.start_datetime)
            event.add('dtend').value = ics_datetime(slot.end_datetime)
            event.add('summary').value = slot.display_name
            ics_description_data = {
                'shift': slot._get_ics_description_data(),
                'is_google_url': False,
            }
            event.add('description').value = self.env['ir.qweb']._render('planning.planning_shift_ics_description', ics_description_data)
        return calendar

    def _get_ics_description_data(self):
        return {
            'name': self.name,
            'allocated_hours': self.allocated_hours,
            'allocated_percentage': self.allocated_percentage,
            'role': self.role_id.name,
        }

    def auto_plan_id(self):
        """ Used in the form view to auto plan a single shift.
        """
        self.ensure_one()
        if not self.with_context(planning_slot_id=self.id).auto_plan_ids([('id', '=', self.id)])['open_shift_assigned']:
            return self._get_notification_action("danger", self.env._("There are no resources available for this open shift."))
        return None

    def _get_open_shifts_resources(self):
        # Get all resources that have the role set on those shifts as default role or in their roles.
        # open_shifts.role_id.ids wouldn't include False, yet we need this information
        open_shift_role_ids = [shift.role_id.id for shift in self]
        resources = self.env['resource.resource'].search(['|', ('default_role_id', 'in', open_shift_role_ids), ('role_ids', 'in', self.role_id.ids)])
        # And make two dictionnaries out of it (default roles and roles). We will prioritize default roles.
        resource_ids_per_role = defaultdict(list)
        resource_ids_per_default_role = defaultdict(list)
        for resource in resources:
            resource_ids_per_default_role[resource.default_role_id].append(resource.id)
            for role in resource.role_ids:
                if role != resource.default_role_id:
                    resource_ids_per_role[role].append(resource.id)
        return resources, [resource_ids_per_default_role, resource_ids_per_role]

    def _get_resources_dict_values(self, resource_dict):
        self.ensure_one()
        resource_ids = resource_dict.get(self.role_id, [])
        shuffle(resource_ids)
        return resource_ids

    @api.model
    def auto_plan_ids(self, view_domain):
        # We need to make sure we have a specified either one shift in particular or a period to look into.
        assert self.env.context.get('planning_slot_id') or (
            self.env.context.get('default_start_datetime') and self.env.context.get('default_end_datetime')
        ), "`default_start_datetime` and `default_end_datetime` attributes should be in the context"

        # Our goal is to assign empty shifts in this period. So first, let's get them all!
        open_shifts, min_start, max_end = self._read_group(
            Domain.AND([
                view_domain,
                [('resource_id', '=', False)],
            ]),
            [],
            ['id:recordset', 'start_datetime:min', 'end_datetime:max'],
        )[0]
        if not open_shifts:
            return {"open_shift_assigned": []}
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        min_start = min_start.astimezone(user_tz)
        max_end = max_end.astimezone(user_tz)

        resources, resources_dicts = open_shifts._get_open_shifts_resources()
        # Get the schedule of each resource in the period.
        flexible_resources = resources.filtered(lambda r: r._is_flexible())
        regular_resources = resources - flexible_resources
        schedule_intervals_per_resource_id, _dummy = regular_resources._get_valid_work_intervals(min_start, max_end)
        locale = babel_locale_parse(get_lang(self.env).code)

        # we assume that if the employee has currently a flexible contract, all other contracts are also flexible
        flexible_resource_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week = flexible_resources._get_flexible_resource_valid_work_intervals(min_start, max_end)
        schedule_intervals_per_resource_id.update(flexible_resource_work_intervals)

        if flexible_resources:
            min_start = weekstart(locale, min_start)
            max_end = weekend(locale, max_end)

        # Now let's get the assigned shifts and count the worked hours per day for each resource
        min_start = min_start.astimezone(pytz.utc).replace(tzinfo=None) + relativedelta(hour=0, minute=0, second=0, microsecond=0)
        max_end = max_end.astimezone(pytz.utc).replace(tzinfo=None) + relativedelta(days=1, hour=0, minute=0, second=0, microsecond=0)
        PlanningShift = self.env['planning.slot']
        same_days_shifts = PlanningShift.search_read([
            ('resource_id', 'in', resources.ids),
            ('end_datetime', '>', min_start),
            ('start_datetime', '<', max_end),
        ], ['start_datetime', 'end_datetime', 'resource_id', 'allocated_hours'], load=False)

        remaining_hours_per_day = deepcopy(flexible_resources_hours_per_day)
        remaining_hours_per_week = deepcopy(flexible_resources_hours_per_week)
        timeline_and_worked_hours_per_resource_id = self._shift_records_to_timeline_per_resource_id(same_days_shifts, flexible_resources, min_start, max_end, remaining_hours_per_day, remaining_hours_per_week, locale)

        # Create an "empty timeline" with midnight for each day in the period
        delta_days = (max_end - min_start).days
        empty_timeline = [
            ((min_start + relativedelta(days=i + 1)).astimezone(user_tz).replace(tzinfo=None), 0)
            for i in range(delta_days)
        ]

        def find_resource(shift):
            shift_intervals = Intervals([(
                shift.start_datetime.astimezone(user_tz),
                shift.end_datetime.astimezone(user_tz),
                PlanningShift,
            )])
            for resources_dict in resources_dicts:
                resource_ids = shift._get_resources_dict_values(resources_dict)
                for resource in self.env['resource.resource'].browse(resource_ids):
                    split_shift_intervals = shift_intervals & schedule_intervals_per_resource_id[resource.id]
                    # If the shift is out of resource's schedule, skip it.
                    if not split_shift_intervals:
                        continue
                    is_flex_resource = resource._is_flexible()
                    if is_flex_resource:
                        work_hours_per_day = defaultdict(float)
                        working_hours = resource._get_flexible_resource_work_hours(split_shift_intervals, flexible_resources_hours_per_day[resource.id], flexible_resources_hours_per_week[resource.id], work_hours_per_day)
                        rate = shift.allocated_hours / working_hours if working_hours > 0.0 else float('inf')

                        is_overloaded = False
                        for day, hours in work_hours_per_day.items():
                            week = weeknumber(locale, day)
                            hours_to_work = hours * rate
                            if hours_to_work > remaining_hours_per_day[resource.id].get(day, 0.0) or hours_to_work > remaining_hours_per_week[resource.id].get(week, 0.0):
                                is_overloaded = True
                                break

                        if is_overloaded:
                            continue
                    else:
                        rate = shift.allocated_hours * 3600 / sum(
                            round((end - start).total_seconds())
                            for start, end, rec in split_shift_intervals
                        )
                    # Try to add the shift to the timeline.
                    timeline = self._get_new_timeline_if_fits_in(
                        split_shift_intervals,
                        rate,
                        resource.calendar_id.hours_per_day if resource.calendar_id else resource.company_id.resource_calendar_id.hours_per_day,
                        timeline_and_worked_hours_per_resource_id[resource.id].copy(),
                        empty_timeline,
                    )
                    # If we got a new timeline (not False), it means the shift fits for the resource
                    # (no overload, no "occupation rate" > 100%).
                    # If it fits, assign the shift to the resource and update the timeline.
                    # If a timeline is found, the resource can work the allocated_hours set on the shift.
                    # so the allocated_percentage is recomputed based on the working calendar of the
                    # resource and the allocated_hours set on the shift.
                    if timeline:
                        original_allocated_hours = shift.allocated_hours
                        shift.resource_id = resource
                        shift._compute_allocated_hours()
                        timeline_and_worked_hours_per_resource_id[resource.id] = timeline
                        start_utc = pytz.utc.localize(shift.start_datetime)
                        end_utc = pytz.utc.localize(shift.end_datetime)
                        if is_flex_resource:
                            resource_work_intervals, resource_hours_per_day, resource_hours_per_week = resource._get_flexible_resource_valid_work_intervals(start_utc, end_utc)
                            hours_needed_to_plan_by_day = defaultdict(float)
                            work_hours = resource._get_flexible_resource_work_hours(resource_work_intervals[resource.id], resource_hours_per_day[resource.id], resource_hours_per_week[resource.id], hours_needed_to_plan_by_day)

                            assert work_hours > 0.0, "it doesn't make sens to have a timeline, then no work hours to plan"
                            rate = original_allocated_hours / work_hours
                            for day, hours in hours_needed_to_plan_by_day.items():
                                remaining_hours_per_day[resource.id][day] -= hours * rate
                                remaining_hours_per_week[resource.id][weeknumber(locale, day)] -= hours * rate
                        else:
                            resource_work_intervals, calendar_work_intervals = shift.resource_id._get_valid_work_intervals(start_utc, end_utc, calendars=shift.company_id.resource_calendar_id)
                            work_hours = shift._get_working_hours_over_period(start_utc, end_utc, resource_work_intervals, calendar_work_intervals)

                        shift.allocated_percentage = 100 * original_allocated_hours / work_hours if work_hours else 100
                        return True
            return False

        return {"open_shift_assigned": open_shifts.filtered(find_resource).ids}

# A. Represent the resoures shifts and the open shift on a timeline
#   Legend
#   ┏━━ : open shift                    ┌─────────────────── 2023/01/02 ────────────────┬─────────────────── 2023/01/03 ────────────────┐
#   ┌── : resource's shifts             0 ───────────── 8 ~~~~~~~~~~~~~ 16 ──────────── 0 ───────────── 8 ~~~~~~~~~~~~~ 16 ──────────── 0
#   ~~~ : resource's schedule           ├───────────────┼───────────────┼───────────────┼───────────────┼───────────────┼───────────────┤

# a/ Allocated Hours (ah) :                             ┏━━ 3h ━┓                                               ┌────── 8h ─────┐
#                                                       ┡━━━━━━━┹────────────────────── 7h ─────────────────────┴───────┬───────┘
#                                                       └───────────────────────────────────────────────────────────────┘

# b/ Rates [ah / (end - start)] :                       ┏━━ 75% ┓                                               ┌───── 100% ────┐
#                                                       ┡━━━━━━━┹───────────────────── 25% ─────────────────────┴───────┬───────┘
#                                                       └───────────────────────────────────────────────────────────────┘

# c/ Increments Timeline :                             ┌↑75%
#   Visual :                                           └↑25%    ↓75%                                            ↑100%   ↓25%    ↓100%
#   Array :                                             ┗━━━━━━━┹───────────────────────────────────────────────┴───────┴───────┘
# [
#    (dt(2023, 1, 2,  8, 0), +1.00),
#    (dt(2023, 1, 2, 12, 0), -0.75),
#    (dt(2023, 1, 3, 12, 0), +1.00),
#    (dt(2023, 1, 3, 16, 0), -0.25),
#    (dt(2023, 1, 3, 20, 0), -1.00),
# ]

# d/ Values Timeline :
#   Visual :                                            |100%   |25%                                            |125%   |100%   |0%
#   Array :                                             ┗━━━━━━━┹───────────────────────────────────────────────┴───────┴───────┘
# [
#    (dt(2023, 1, 2,  8, 0),  1.00),
#    (dt(2023, 1, 2, 12, 0),  0.25),
#    (dt(2023, 1, 3, 12, 0),  1.25),
#    (dt(2023, 1, 3, 16, 0),  1.00),
#    (dt(2023, 1, 3, 20, 0),  0.00),
# ]

# B. Try to assign each open shift to a resource

# 1) Check that the shift fits in the resource's schedule
#   We just get the schedule intervals of the resource, convert the shift to intervals, and check the difference.

# 2) Check that the resource would not be overloaded this day
#   Delimit days with ghost events at 0:00. Then compute the total time worked per day and compare it to the resource's max load.
#   We do so considering that every resource have the same time zone (the user's one).

# 3) ...and that it would not conflict with the resource's other shifts (sum of rates > 100%)
#   Visual :                            |0%             |100%   |25%                    |25%                    |125%   |100%   |0%     |0%
#   Array :                             └────── A ──────┗━━ B ━━┹────────── C ──────────┴───────────────────────┴───────┴───────┴───────┘
# [                                     ^                                               ^                                               ^
#    (dt(2023, 1, 2,  0, 0),  0.00), <
#    (dt(2023, 1, 2,  8, 0),  1.25),                         2) Worked Hours on 2023/01/02
#    (dt(2023, 1, 2, 12, 0),  0.25),                            = 8h * 0% (A) + 4h * 125% (B) + 12h * 25% (C)
#    (dt(2023, 1, 3,  0, 0),  0.25), <                          = 0h          + 5h            + 3h
#    (dt(2023, 1, 3, 12, 0),  1.00),                            = 8h => OK
#    (dt(2023, 1, 3, 16, 0),  0.75),
#    (dt(2023, 1, 3, 20, 0),  0.00),                         3) rate(B) = 100% => OK
#    (dt(2023, 1, 4,  0, 0),  0.00), <
# ]

    @api.model
    def _shift_records_to_timeline_per_resource_id(self, records, flexible_resources, min_start, max_end, remaining_hours_per_day, remaining_hours_per_week, locale):
        timeline_and_worked_hours_per_resource_id = defaultdict(list)
        resource_by_id = {}
        flexible_resource_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week = flexible_resources._get_flexible_resource_valid_work_intervals(pytz.utc.localize(min_start), pytz.utc.localize(max_end))

        for record in records:
            start, end = record['start_datetime'], record['end_datetime']
            resource_id = record['resource_id']
            allocated_hours = record['allocated_hours']

            if resource_id not in flexible_resources.ids:
                rate = allocated_hours * 3600 / (
                    fields.Datetime.from_string(record['end_datetime']) - fields.Datetime.from_string(record['start_datetime'])
                ).total_seconds() / 3600
            else:
                record_intervals = Intervals([(pytz.utc.localize(start), pytz.utc.localize(end), set())]) & flexible_resource_work_intervals[resource_id]
                work_hours_per_day = defaultdict(float)
                if resource_id not in resource_by_id:
                    resource_by_id[resource_id] = self.env['resource.resource'].browse(resource_id)

                work_hours = resource_by_id[resource_id]._get_flexible_resource_work_hours(record_intervals, flexible_resources_hours_per_day[resource_id], flexible_resources_hours_per_week[resource_id], work_hours_per_day)
                rate = allocated_hours / work_hours if work_hours > 0.0 else float('inf')

                for day, hours in work_hours_per_day.items():
                    remaining_hours_per_day[resource_id][day] -= rate * hours
                    remaining_hours_per_week[resource_id][weeknumber(locale, day)] -= rate * hours

            timeline_and_worked_hours_per_resource_id[resource_id].extend([
                (start, rate), (end, -rate)
            ])
        for resource_id, timeline in timeline_and_worked_hours_per_resource_id.items():
            timeline_and_worked_hours_per_resource_id[resource_id] = self._increments_to_values(timeline)
        return timeline_and_worked_hours_per_resource_id

    @api.model
    def _get_new_timeline_if_fits_in(self, split_shift_intervals, rate, resource_hours_per_day, timeline, empty_timeline):
        if rate > 1:
            return False
        add_midnights = True
        for split_shift_start, split_shift_end, _ in split_shift_intervals:
            start = split_shift_start.astimezone(pytz.utc).replace(tzinfo=None)
            end = split_shift_end.astimezone(pytz.utc).replace(tzinfo=None)
            increments = self._values_to_increments(timeline) + [(start, rate), (end, -rate)]
            if add_midnights:
                # Add ghost events at 0:00 to delimit days. This condition prevents from adding ghost events on each iteration.
                increments += empty_timeline
                add_midnights = False
            timeline = self._increments_to_values(increments, check=(start, end, resource_hours_per_day))
            if not timeline:
                return False
        return timeline

    @api.model
    def _increments_to_values(self, increments, check=False):
        """ Transform a timeline of increments into a timeline of values by accumulating the increments.
            If check is a tuple (start, end, resource_hours_per_day), the timeline is checked to ensure
            that the resource would not be overloaded this day or have an "occupation rate" > 100% between start and end.

            :param increments: List of tuples (instant, increment).
            :param check: False or a tuple (start, end, resource_hours_per_day).
            :return: List of tuples (instant, value) if check is False or the timeline is valid, else False.
        """
        if not increments:
            return []
        if check:
            start, end, _dummy = check

        values = []
        # Sum and sort increments by instant.
        increments_sum_per_instant = defaultdict(float)
        for instant, increment in increments:
            increments_sum_per_instant[instant] += increment
        increments = list(increments_sum_per_instant.items())
        increments.sort(key=lambda increment: increment[0])
        last_instant, last_value = increments[0][0], 0.0
        for increment in increments:
            last_value += increment[1]
            last_instant = increment[0]
            # Check if the occupation rate exceeds 100%.
            if check and last_value > 1 and start <= last_instant <= end:
                return False
            values.append((last_instant, last_value))
        return values

    @api.model
    def _values_to_increments(self, values):
        """ Transform a timeline of values into a timeline of increments by subtracting the values.

            :param values: List of tuples (instant, value).
            :return: List of tuples (instant, increment).
        """
        increments = []
        last_value = 0
        for value in values:
            increments.append((value[0], value[1] - last_value))
            last_value = value[1]
        return increments

    @api.model
    def action_rollback_auto_plan_ids(self, shifts_data):
        open_shift_assigned = shifts_data["open_shift_assigned"]
        self.browse(open_shift_assigned).resource_id = False

    # ----------------------------------------------------
    # Gantt - Calendar view
    # ----------------------------------------------------

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=None, progress_bar_fields=None, start_date=None, stop_date=None, scale=None):
        result = super(PlanningSlot, self.with_context(scale=scale)).get_gantt_data(domain, groupby, read_specification, limit=limit, offset=offset, unavailability_fields=unavailability_fields, progress_bar_fields=progress_bar_fields, start_date=start_date, stop_date=stop_date, scale=scale)
        if "resource_id" in groupby:
            result["working_periods"] = self._gantt_resource_employees_working_periods(result["groups"], start_date, stop_date)
        return result

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        if field != "resource_id":
            return super()._gantt_unavailability(field, res_ids, start, stop, scale)

        resources = self.env['resource.resource'].browse(res_ids).filtered('calendar_id')
        leaves_mapping = resources._get_unavailable_intervals(start, stop)
        company_leaves = self.env.company.resource_calendar_id._unavailable_intervals(start.replace(tzinfo=pytz.utc), stop.replace(tzinfo=pytz.utc))
        cell_dt = timedelta(hours=1) if scale in ['day', 'week'] else timedelta(hours=12)

        result = {False: []}
        for resource in resources:
            # return no unavailability if the resource is fully flexible hours (both material and employee).
            if (resource.id not in res_ids) or (resource and resource._is_fully_flexible()):
                continue
            calendar = leaves_mapping.get(resource.id, company_leaves)
            # remove intervals smaller than a cell, as they will cause half a cell to turn grey
            # ie: when looking at a week, a employee start everyday at 8, so there is a unavailability
            # like: 2019-05-22 20:00 -> 2019-05-23 08:00 which will make the first half of the 23's cell grey
            notable_intervals = filter(lambda interval: interval[1] - interval[0] >= cell_dt, calendar)
            result[resource.id] = [{'start': interval[0], 'stop': interval[1]} for interval in notable_intervals]

        return result

    @api.model
    def get_unusual_days(self, date_from, date_to=None):
        return self.env.user.employee_id._get_unusual_days(date_from, date_to)

    # ----------------------------------------------------
    # Period Duplication
    # ----------------------------------------------------

    @api.model
    def action_copy_previous_week(self, date_start_week, view_domain):
        date_end_copy = datetime.strptime(date_start_week, DEFAULT_SERVER_DATETIME_FORMAT)
        date_start_copy = date_end_copy - relativedelta(days=7)
        domain = [
            ('recurrency_id', '=', False),
            ('was_copied', '=', False)
        ]
        for dom in view_domain:
            if dom in ['|', '&', '!']:
                domain.append(dom)
            elif dom[0] == 'start_datetime':
                domain.append(('start_datetime', '>=', date_start_copy))
            elif dom[0] == 'end_datetime':
                domain.append(('end_datetime', '<=', date_end_copy))
            else:
                domain.append(tuple(dom))
        slots_to_copy = self.search(domain)

        new_slot_values = []
        new_slot_values = slots_to_copy._copy_slots(date_start_copy, date_end_copy, relativedelta(days=7))
        slots_to_copy.write({'was_copied': True})
        if new_slot_values:
            return [self.create(new_slot_values).ids, slots_to_copy.ids]
        return False

    def action_rollback_copy_previous_week(self, copied_slot_ids):
        self.browse(copied_slot_ids).was_copied = False
        self.unlink()

    # ----------------------------------------------------
    # Sending Shifts
    # ----------------------------------------------------

    def get_employees_without_work_email(self):
        """ Check if the employees to send the slot have a work email set.

            This method is used in a rpc call.

            :returns: a dictionnary containing the all needed information to continue the process.
                Returns None, if no employee or all employees have an email set.
        """
        self.ensure_one()
        if not self.employee_id.has_access('write'):
            return None
        employees = self.employee_id or self._get_employees_to_send_slot()
        employee_ids_without_work_email = employees.filtered(lambda employee: not employee.work_email).ids
        if not employee_ids_without_work_email:
            return None
        context = dict(self.env.context)
        context['force_email'] = True
        context['form_view_ref'] = 'planning.hr_employee_view_form_email'
        return {
            'relation': 'hr.employee',
            'res_ids': employee_ids_without_work_email,
            'context': context,
        }

    def _get_employees_to_send_slot(self):
        self.ensure_one()
        if not self.employee_id or not self.employee_id.work_email:
            domain = Domain('company_id', '=', self.company_id.id) & Domain('work_email', '!=', False)
            if self.role_id:
                domain &= Domain('planning_role_ids', '=', False) | Domain('planning_role_ids', 'in', self.role_id.id)
            return self.env['hr.employee'].sudo().search(domain)
        return self.employee_id

    def _get_notification_action(self, notif_type, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': notif_type,
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_planning_publish_and_send(self):
        notif_type = "success"
        start, end = min(self.mapped('start_datetime')), max(self.mapped('end_datetime'))
        if all(shift.state == 'published' for shift in self) or not start or not end:
            notif_type = "warning"
            message = self.env._('There are no shifts to publish and send.')
        else:
            planning = self.env['planning.planning'].create({
                'start_datetime': start,
                'end_datetime': end,
            })
            planning._send_planning(slots=self, employees=self.employee_id)
            message = self.env._('The shifts have successfully been published and sent.')
        return self._get_notification_action(notif_type, message)

    def action_send(self):
        self.ensure_one()
        if not self.employee_id or not self.employee_id.work_email:
            self.state = 'published'
        employee_ids = self._get_employees_to_send_slot()
        self._send_slot(employee_ids, self.start_datetime, self.end_datetime)
        message = self.env._("Shift sent")
        return self._get_notification_action('success', message)

    def action_save_template(self):
        """ Used to save template of a shift."""
        self.ensure_one()
        if self.allow_template_creation:
            self.template_creation = True

    def action_unpublish(self):
        if not self.env.user.has_group('planning.group_planning_manager'):
            raise AccessError(self.env._('You are not allowed to reset shifts to draft.'))
        published_shifts = self.filtered(lambda shift: shift.state == 'published' and shift.resource_type != 'material')
        if published_shifts:
            published_shifts.write({'state': 'draft', 'publication_warning': False})
            notif_type = "success"
            message = self.env._('Shifts reset to draft')
        else:
            notif_type = "warning"
            message = self.env._('There are no shifts to reset to draft.')
        return self._get_notification_action(notif_type, message)

    # ----------------------------------------------------
    # Print planning
    # ----------------------------------------------------
    def _print_planning_get_fields_to_copy(self):
        return ['employee_id', 'company_id', 'allocated_percentage', 'allocated_hours', 'resource_id', 'start_datetime', 'end_datetime', 'role_id']

    def _print_planning_get_slot_title(self, slot_start, slot_end, tz_info, group_by):
        def print_planning_format_time(date, tz_info):
            return format_time(self.env, date.time(), tz_info, 'HH:mm')

        allocated_hours_formatted = ""
        if self.allocated_percentage != 100:
            (unitary_part, decimal_part) = float_utils.float_split_str(
                self.allocated_hours,
                precision_digits=2,
            )
            allocated_hours_formatted = f" ({unitary_part}h{decimal_part if decimal_part != '00' else ''})"
        name_get = ""
        if group_by == "role_id":
            if self.resource_id:
                name_get = f" {self.resource_id.name}"
        elif group_by == "resource_id":
            if self.role_id:
                name_get = f" {self.role_id.name}"
        else:
            name_get = f" {self.resource_id.name}" if self.resource_id else ""
            if self.role_id:
                if name_get:
                    name_get += f" - {self.role_id.name}"
                else:
                    name_get = f" {self.role_id.name}"

        return f"{print_planning_format_time(slot_start, tz_info)} – {print_planning_format_time(slot_end, tz_info)}{allocated_hours_formatted}{name_get}"

    @api.model
    def action_print_plannings(self, date_start, date_end, group_bys, domain):

        def print_planning_split_fake_pill(shift, values):
            shift.ensure_one()
            assert 'start_datetime' in values and 'end_datetime' in values and not shift._origin
            record = print_planning_create_fake_pill(shift, {'start_datetime': values.get('start_datetime').astimezone(pytz.utc).replace(tzinfo=None)})
            shift.update({'end_datetime': values.get('end_datetime').astimezone(pytz.utc).replace(tzinfo=None)})
            return record

        def print_planning_create_fake_pill(shift, vals=None):
            record = self.env['planning.slot'].new({
                **shift._read_format(shift._print_planning_get_fields_to_copy())[0],
                **(vals or {}),
            })
            # copy method called inside the original split_pill method recomputes the allocated_hours again after the split (dates changed)
            record._compute_allocated_hours()
            return record

        def print_planning_get_fake_pill_datetime(datetime_per_resource_per_day, resource_id, day, tz_info, default):
            if day in datetime_per_resource_per_day[resource_id]:
                return datetime_per_resource_per_day[resource_id][day].astimezone(tz_info)

            return tz_info.localize(datetime.combine(day, default))

        def print_planning_get_fake_pill_start_datetime(start_datetime_per_resource_per_day, resource_id, day, tz_info):
            return print_planning_get_fake_pill_datetime(start_datetime_per_resource_per_day, resource_id, day, tz_info, time.min)

        def print_planning_get_fake_pill_end_datetime(end_datetime_per_resource_per_day, resource_id, day, tz_info):
            return print_planning_get_fake_pill_datetime(end_datetime_per_resource_per_day, resource_id, day, tz_info, time.max)

        def print_planning_add_slot(shift, tz_info, group_by_slots_per_day_per_week, group, weeks, group_by):
            if float_utils.float_is_zero(shift.allocated_hours, precision_digits=2):
                return

            slot_start = shift.start_datetime.astimezone(tz_info)
            slot_end = shift.end_datetime.astimezone(tz_info)
            date = format_date(self.env, slot_start)
            for index, week, _dummy in weeks:
                if date in week:
                    group_by_slots_per_day_per_week[index][group][date].append({
                        "title": shift._print_planning_get_slot_title(slot_start, slot_end, tz_info, group_by),
                        "style": f"background-color: {shift.role_id._get_light_color(0.5, not shift.resource_id)};"
                    })
                    return

        def print_planning_update_datetime(_datetime, resource_id, datetime_per_resource_per_day, func):
            day = _datetime.date()
            if day in datetime_per_resource_per_day[resource_id]:
                datetime_per_resource_per_day[resource_id][day] = func(datetime_per_resource_per_day[resource_id][day], _datetime)
            else:
                datetime_per_resource_per_day[resource_id][day] = _datetime

        def print_planning_flexible_resources_work_intervals(start, end, resources):
            assert all(resource._is_flexible() and not resource._is_fully_flexible() for resource in resources)
            return {resource.id: Intervals([(start, end, self.env['resource.calendar.attendance'])]) for resource in resources}

        group_bys = [g for g in (group_bys or []) if self.fields_get(g)[g.split(':')[0]]['type'] not in {"datetime", "date"}]
        if not group_bys:
            group_bys = ['resource_id']

        group_by = group_bys[-1]
        date_start = datetime.strptime(date_start, DEFAULT_SERVER_DATETIME_FORMAT)
        date_end = datetime.strptime(date_end, DEFAULT_SERVER_DATETIME_FORMAT)

        if date_end < date_start:
            date_start, date_end = date_end, date_start

        group_by_slots = self.env['planning.slot']._read_group(
            domain,
            [group_by],
            ['id:recordset'],
        )

        if not group_by_slots:
            return False

        tz_info = pytz.timezone(self._get_tz())
        day_start_in_user_tz = date_start.astimezone(tz_info).date()
        day_end_in_user_tz = date_end.astimezone(tz_info).date()
        days_count = (day_end_in_user_tz - day_start_in_user_tz).days + 1
        days = [day_start_in_user_tz + timedelta(days=i) for i in range(days_count)]
        group_by_slots_per_day_per_week = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        unassigned = self.env._("Open Shifts") if group_by == 'resource_id' else self.env._("Undefined %(group)s", group=self.fields_get(group_by)[group_by]["string"])
        group_by_name_by_id = {}
        non_flexible_resources_ids = set()
        flexible_resources_ids = set()

        for g, slots in group_by_slots:
            group_by_name_by_id[g.id if g else False] = g.display_name if g else unassigned
            for slot in slots:
                if slot.resource_id:
                    (flexible_resources_ids if not slot.resource_id._is_fully_flexible() and slot.resource_id._is_flexible() else non_flexible_resources_ids).add(slot.resource_id.id)

        non_flexible_resources = self.env['resource.resource'].browse(non_flexible_resources_ids)
        flexible_resources = self.env['resource.resource'].browse(flexible_resources_ids)

        start_utc, end_utc = pytz.utc.localize(date_start), pytz.utc.localize(date_end)
        resources_work_intervals, _dummy = non_flexible_resources._get_valid_work_intervals(
            start_utc, end_utc
        )

        resources_work_intervals.update(print_planning_flexible_resources_work_intervals(start_utc, end_utc, flexible_resources))

        weeks = [
            (
                int(i / 7),
                [format_date(self.env, day) for day in days[i:i + 7]],
                self.env._(
                    "Week from %(start_date)s to %(end_date)s",
                    start_date=format_date(self.env, days[i:i + 7][0]),
                    end_date=format_date(self.env, days[i:i + 7][-1])
                ),
            )
            for i in range(0, len(days), 7)
        ]

        start_datetime_per_resource_per_day, end_datetime_per_resource_per_day = defaultdict(dict), defaultdict(dict)
        for resource_id, intervals in resources_work_intervals.items():
            for start_datetime, end_datetime, _dummy in intervals._items:
                print_planning_update_datetime(start_datetime, resource_id, start_datetime_per_resource_per_day, min)
                print_planning_update_datetime(end_datetime, resource_id, end_datetime_per_resource_per_day, max)

        for group_id, slots in sorted(group_by_slots, key=lambda x: x[0].display_name if x[0] else ''):
            group = group_id.id if group_id else False
            for slot in slots:
                resource_id = slot.resource_id
                slot_start = slot.start_datetime.astimezone(tz_info)
                slot_end = slot.end_datetime.astimezone(tz_info)

                slot_start_day = slot_start.date()
                slot_end_day = slot_end.date()

                # one day slot
                if slot_start_day == slot_end_day:
                    print_planning_add_slot(slot, tz_info, group_by_slots_per_day_per_week, group, weeks, group_by)
                else:
                    # slot on more than one day, we do a fake copy using new without storing in db and
                    # we use split_pill function to cut the slot in many days
                    fake_slot = print_planning_create_fake_pill(slot)

                    # remove the part of the pill happening in the previous weeks
                    first_day = days[0]
                    if slot_start_day < first_day:
                        fake_slot = print_planning_split_fake_pill(fake_slot, {
                            "start_datetime": print_planning_get_fake_pill_start_datetime(start_datetime_per_resource_per_day, resource_id.id, first_day, tz_info),
                            "end_datetime": print_planning_get_fake_pill_end_datetime(end_datetime_per_resource_per_day, resource_id.id, first_day + timedelta(days=-1), tz_info)
                        })

                    # remove the part of the pill happening in the next weeks
                    last_day = days[-1]
                    if slot_end_day > last_day:
                        print_planning_split_fake_pill(fake_slot, {
                            "start_datetime": print_planning_get_fake_pill_start_datetime(start_datetime_per_resource_per_day, resource_id.id, last_day + timedelta(days=1), tz_info),
                            "end_datetime": print_planning_get_fake_pill_end_datetime(end_datetime_per_resource_per_day, resource_id.id, last_day, tz_info),
                        })

                    # split the pill in different pills, pill per day
                    current_day = fake_slot.start_datetime.date()
                    last_day = fake_slot.end_datetime.date()
                    while current_day < last_day:
                        split_slot = print_planning_split_fake_pill(fake_slot, {
                            "start_datetime": print_planning_get_fake_pill_start_datetime(start_datetime_per_resource_per_day, resource_id.id, current_day + timedelta(days=1), tz_info),
                            "end_datetime": print_planning_get_fake_pill_end_datetime(end_datetime_per_resource_per_day, resource_id.id, current_day, tz_info),
                        })

                        print_planning_add_slot(fake_slot, tz_info, group_by_slots_per_day_per_week, group, weeks, group_by)
                        fake_slot = split_slot
                        current_day += timedelta(days=1)

                    print_planning_add_slot(fake_slot, tz_info, group_by_slots_per_day_per_week, group, weeks, group_by)

        # groups were inserted in the dict in a specific order (false, then sorted non DESC order)
        # but in Qweb, the order was lost
        # so we transformed it to a dict {week: (group, {day: slots})}
        group_by_slots_per_day_per_week_formatted = {
            week: [(group, val) for group, val in data.items()]
            for week, data in group_by_slots_per_day_per_week.items()
        }

        return self.env.ref('planning.report_planning_slot').with_context(discard_logo_check=True).report_action(None,
            data={
                'group_by_slots_per_day_per_week': group_by_slots_per_day_per_week_formatted,
                'weeks': weeks,
                'group_by_name_by_id': group_by_name_by_id,
            }
        )

    # ----------------------------------------------------
    # Business Methods
    # ----------------------------------------------------

    def _calculate_slot_duration(self):
        self.ensure_one()
        if not self.start_datetime or not self.end_datetime:
            return 0.0

        period = self.end_datetime - self.start_datetime
        if self.resource_id:
            start = pytz.utc.localize(self.start_datetime).astimezone(pytz.timezone(self.resource_id.tz))
            end = pytz.utc.localize(self.end_datetime).astimezone(pytz.timezone(self.resource_id.tz))
            if self.resource_id._is_flexible():
                work_intervals, hours_per_day, hours_per_week = self.resource_id._get_flexible_resource_valid_work_intervals(start, end)
                slot_duration = self.resource_id._get_flexible_resource_work_hours(work_intervals[self.resource_id.id], hours_per_day[self.resource_id.id], hours_per_week[self.resource_id.id])
            else:
                work_intervals, _dummy = self.resource_id._get_valid_work_intervals(start, end)
                slot_duration = sum_intervals(work_intervals[self.resource_id.id])
        else:
            slot_duration = period.total_seconds() / 3600
        # if the resource is an employee, the hours_per_day of its calendar is used as max_hours_per_day.
        if self.employee_id:
            max_hours_per_day = self.employee_id.resource_calendar_id.hours_per_day
        # For other resource and open shifts, we refer to the max of the company's default contract
        else:
            max_hours_per_day = self.company_id.resource_calendar_id.hours_per_day
        max_duration = (period.days + (1 if period.seconds else 0)) * max_hours_per_day
        if not max_duration or max_duration >= slot_duration:
            return slot_duration
        return max_duration

    # ----------------------------------------------------
    # Copy Slots
    # ----------------------------------------------------

    def _add_delta_with_dst(self, start, delta):
        """
        Add to start, adjusting the hours if needed to account for a shift in the local timezone between the
        start date and the resulting date (typically, because of DST)

        :param start: origin date in UTC timezone, but without timezone info (a naive date)
        :return resulting date in the UTC timezone (a naive date)
        """
        try:
            tz = pytz.timezone(self._get_tz())
        except pytz.UnknownTimeZoneError:
            tz = pytz.UTC
        start = start.replace(tzinfo=pytz.utc).astimezone(tz).replace(tzinfo=None)
        result = start + delta
        return tz.localize(result).astimezone(pytz.utc).replace(tzinfo=None)

    def _init_remaining_hours_to_plan(self, remaining_hours_to_plan):
        """
            Inits the remaining_hours_to_plan dict for a given slot and returns wether
            there are enough remaining hours.

            :return a bool representing wether or not there are still hours remaining
        """
        self.ensure_one()
        return True

    def _update_remaining_hours_to_plan_and_values(self, remaining_hours_to_plan, values):
        """
            Update the remaining_hours_to_plan with the allocated hours of the slot in `values`
            and returns wether there are enough remaining hours.

            If remaining_hours is strictly positive, and the allocated hours of the slot in `values` is
            higher than remaining hours, than update the values in order to consume at most the
            number of remaining_hours still available.

            :return a bool representing wether or not there are still hours remaining
        """
        self.ensure_one()
        return True

    def _get_split_slot_values(self, values, intervals, remaining_hours_to_plan, unassign=False):
        """
            Generates and returns slots values within the given intervals

            The slot in values, which represents a forecast planning slot, is split in multiple parts
            filling the (available) intervals.

            :return a vals list of the slot to create
        """
        self.ensure_one()
        split_slot_values = []
        for start_inter, end_inter, _resource in intervals:
            new_slot_vals = {
                **values,
                'start_datetime': start_inter.astimezone(pytz.utc).replace(tzinfo=None),
                'end_datetime': end_inter.astimezone(pytz.utc).replace(tzinfo=None),
            }
            was_updated = self._update_remaining_hours_to_plan_and_values(remaining_hours_to_plan, new_slot_vals)
            period = end_inter - start_inter
            slot_duration = period.total_seconds() / 3600
            # If the slot is assigned to a flexible resource, the allocated hours are computed based on the hours_per_day of the resource calendar
            # However if it's a fully flexible resource, the allocated hours are the same as the slot duration.
            if (
                not unassign
                and self.resource_id._is_flexible() and
                not self.resource_id._is_fully_flexible()
            ):
                # refer to the hours_per_day if the slot duration exceeds it.
                max_hours_per_day = self.employee_id.resource_calendar_id.hours_per_day
                max_duration = (period.days + (1 if period.seconds else 0)) * max_hours_per_day
                slot_duration = min(slot_duration, max_duration)
            new_slot_vals['allocated_hours'] = float_utils.float_round(
                slot_duration * (self.allocated_percentage / 100.0),
                precision_digits=2
            )
            if not was_updated:
                return split_slot_values
            if unassign:
                new_slot_vals['resource_id'] = False
            split_slot_values.append(new_slot_vals)
        return split_slot_values

    def _copy_slots(self, start_dt, end_dt, delta):
        """
            Copy slots planned between `start_dt` and `end_dt`, after a `delta`

            Takes into account the resource calendar and the slots already planned.
            All the slots will be copied, whatever the value of was_copied is.

            :return a vals list of the slot to create
        """
        # 1) Retrieve all the slots of the new period and create intervals within the slots will have to be unassigned (resource_slots_intervals),
        #    add it to `unavailable_intervals_per_resource`
        # 2) Retrieve all the calendars for the resource and their validity intervals (intervals within which the calendar is valid for the resource)
        # 3) For each calendar, retrieve the attendances and the leaves. Add attendances by resource in `attendance_intervals_per_resource` and
        #    the leaves by resource in `unavailable_intervals_per_resource`
        # 4) For each slot, check if the slot is at least within an attendance and outside a company leave :
        #    - If it is a planning :
        #       - Copy it if the resource is available
        #       - Copy and unassign it if the resource isn't available
        #    - Otherwise :
        #       - Split it and assign the part within resource work intervals
        #       - Split it and unassign the part within resource leaves and outside company leaves
        resource_per_calendar = defaultdict(lambda: self.env['resource.resource'])
        resource_calendar_validity_intervals = defaultdict(dict)
        attendance_intervals_per_resource = defaultdict(Intervals)  # key: resource, values: attendance intervals
        unavailable_intervals_per_resource = defaultdict(Intervals)  # key: resource, values: unavailable intervals
        attendance_intervals_per_calendar = defaultdict(Intervals)  # key: calendar, values: attendance intervals (used for company calendars)
        leave_intervals_per_calendar = defaultdict(Intervals)  # key: calendar, values: leave intervals (used for company calendars)
        new_slot_values = []
        # date utils variable
        start_dt_delta = start_dt + delta
        end_dt_delta = end_dt + delta
        start_dt_delta_utc = pytz.utc.localize(start_dt_delta)
        end_dt_delta_utc = pytz.utc.localize(end_dt_delta)
        # 1)
        # Search for all resource slots already planned
        resource_slots = self.search([
            ('start_datetime', '>=', start_dt_delta),
            ('end_datetime', '<=', end_dt_delta),
            ('resource_id', 'in', self.resource_id.ids)
        ])
        # And convert it into intervals
        for slot in resource_slots:
            unavailable_intervals_per_resource[slot.resource_id] |= Intervals([(
                pytz.utc.localize(slot.start_datetime),
                pytz.utc.localize(slot.end_datetime),
                self.env['resource.calendar.leaves'])])
        # 2)
        resource_calendar_validity_intervals = self.resource_id.sudo().filtered(lambda resource: not resource._is_flexible())._get_calendars_validity_within_period(
            start_dt_delta_utc, end_dt_delta_utc)
        for slot in self:
            if slot.resource_id:
                for calendar in resource_calendar_validity_intervals[slot.resource_id.id]:
                    resource_per_calendar[calendar] |= slot.resource_id
            company_calendar_id = slot.company_id.resource_calendar_id
            resource_per_calendar[company_calendar_id] |= self.env['resource.resource']  # ensures the company_calendar will be in resource_per_calendar keys.
        # 3)
        for calendar, resources in resource_per_calendar.items():
            # For empty calendar (fully flexible resource), we do not need to retrieve the attendances nor the leaves.
            if not calendar:
                continue
            # For each calendar, retrieves the work intervals of every resource
            attendances = {
                resource_id: Intervals(work_interval._items)
                for resource_id, work_interval in calendar._attendance_intervals_batch(
                    start_dt_delta_utc,
                    end_dt_delta_utc,
                    resources=resources
                ).items()
            }
            leaves = calendar._leave_intervals_batch(
                start_dt_delta_utc,
                end_dt_delta_utc,
                resources=resources
            )
            attendance_intervals_per_calendar[calendar] = attendances[False]
            leave_intervals_per_calendar[calendar] = leaves[False]
            for resource in resources:
                # for each resource, adds his/her attendances and unavailabilities for this calendar, during the calendar validity interval.
                attendance_intervals_per_resource[resource] |= (attendances[resource.id] & resource_calendar_validity_intervals[resource.id][calendar])
                unavailable_intervals_per_resource[resource] |= (leaves[resource.id] & resource_calendar_validity_intervals[resource.id][calendar])
        # 4)
        remaining_hours_to_plan = {}
        for slot in self:
            if not slot._init_remaining_hours_to_plan(remaining_hours_to_plan):
                continue
            values = slot.copy_data(default={'state': 'draft'})[0]
            if not values.get('start_datetime') or not values.get('end_datetime'):
                continue
            values['start_datetime'] = slot._add_delta_with_dst(values['start_datetime'], delta)
            values['end_datetime'] = slot._add_delta_with_dst(values['end_datetime'], delta)
            if slot.allocation_type == 'forecast' and (not slot.resource_id or slot.resource_id._is_fully_flexible()):
                new_slot_values.append(values)
                continue
            if any(
                new_slot['resource_id'] == values['resource_id'] and
                new_slot['start_datetime'] <= values['end_datetime'] and
                new_slot['end_datetime'] >= values['start_datetime']
                for new_slot in new_slot_values
            ):
                values['resource_id'] = False
            interval = Intervals([(
                pytz.utc.localize(values.get('start_datetime')),
                pytz.utc.localize(values.get('end_datetime')),
                self.env['resource.calendar.attendance']
            )])
            company_calendar = slot.company_id.resource_calendar_id
            # Check if interval is contained in the resource work interval.
            # For flexible hours, ignore the resource work interval and return the whole interval of slot as valid.
            if slot.resource_id and slot.resource_id._is_flexible():
                attendance_interval_resource = interval
                attendance_interval_company = interval
            else:
                attendance_resource = attendance_intervals_per_resource[slot.resource_id] if slot.resource_id else attendance_intervals_per_calendar[company_calendar]
                attendance_interval_resource = interval & attendance_resource
                # Check if interval is contained in the company attendances interval
                attendance_interval_company = interval & attendance_intervals_per_calendar[company_calendar]
            # Check if interval is contained in the company leaves interval
            unavailable_interval_company = interval & leave_intervals_per_calendar[company_calendar]
            unavailable_interval_resource = unavailable_interval_company if not slot.resource_id else (interval & unavailable_intervals_per_resource[slot.resource_id])
            if not unavailable_interval_company:
                # Either the employee has, at least, some attendance that are not during the company unavailability
                # Either the company has, at least, some attendance that are not during the company unavailability

                if slot.allocation_type == 'planning':
                    # /!\ It can be an "Extended Attendance" (see hereabove), and the slot may be unassigned.
                    if unavailable_interval_resource or not attendance_interval_resource:
                        # if the slot is during an resourece unavailability, or the employee is not attending during the slot
                        if slot.resource_type != 'user':
                            # if the resource is not an employee and the resource is not available, do not copy it nor unassign it
                            continue
                        values['resource_id'] = False
                    if not slot._update_remaining_hours_to_plan_and_values(remaining_hours_to_plan, values):
                        # make sure the hours remaining are enough
                        continue
                    new_slot_values.append(values)
                else:
                    if attendance_interval_resource:
                        # if the resource has attendances, at least during a while of the future slot lifetime,
                        # 1) Work interval represents the availabilities of the employee
                        # 2) The unassigned intervals represents the slots where the employee should be unassigned
                        #    (when the company is not unavailable and the employee is unavailable)
                        work_interval_employee = (attendance_interval_resource - unavailable_interval_resource)
                        unassigned_interval = (unavailable_interval_resource - unavailable_interval_company) & (attendance_interval_company - unavailable_interval_company)
                        split_slot_values = slot._get_split_slot_values(values, work_interval_employee, remaining_hours_to_plan)
                        if slot.resource_type == 'user':
                            split_slot_values += slot._get_split_slot_values(values, unassigned_interval, remaining_hours_to_plan, unassign=True)
                    elif slot.resource_type != 'user':
                        # If the resource type is not user and the slot can not be assigned to the resource, do not copy not unassign it
                        continue
                    else:
                        # When the employee has no attendance at all, we are in the case where the employee has a calendar different than the
                        # company (or no more calendar), so the slot will be unassigned
                        unassigned_interval = attendance_interval_company - unavailable_interval_company
                        split_slot_values = slot._get_split_slot_values(values, unassigned_interval, remaining_hours_to_plan, unassign=True)
                    # merge forecast slots in order to have visually bigger slots
                    new_slot_values += self._merge_slots_values(split_slot_values, unassigned_interval)
        return new_slot_values

    def _display_name_fields(self):
        """ List of fields that can be displayed in the display_name """
        return ['resource_id', 'role_id']

    def _get_fields_breaking_publication(self):
        """ Fields list triggering the `publication_warning` to True when updating shifts """
        return [
            'resource_id',
            'resource_type',
            'start_datetime',
            'end_datetime',
            'role_id',
        ]

    @api.model
    def _get_template_fields(self):
        # key -> field from template
        # value -> field from slot
        return {'role_id': 'role_id', 'start_time': 'start_datetime', 'end_time': 'end_datetime', 'duration_days': 'working_days_count'}

    def _get_tz(self):
        return (self.env.user.tz
                or self.employee_id.tz
                or self.resource_id.tz
                or self.env.context.get('tz')
                or self.company_id.resource_calendar_id.tz
                or 'UTC')

    def _prepare_template_values(self):
        """ extract values from shift to create a template """
        # compute duration w/ tzinfo otherwise DST will not be taken into account
        destination_tz = pytz.timezone(self._get_tz())
        start_datetime = pytz.utc.localize(self.start_datetime).astimezone(destination_tz)
        end_datetime = pytz.utc.localize(self.end_datetime).astimezone(destination_tz)

        # get days span from slot
        duration_days = days_span(start_datetime, end_datetime)

        return {
            'start_time': start_datetime.hour + start_datetime.minute / 60.0,
            'end_time': end_datetime.hour + end_datetime.minute / 60.0,
            'duration_days': duration_days,
            'role_id': self.role_id.id
        }

    def _manage_archived_resources(self, departure_date):
        shift_vals_list = []
        shift_ids_to_remove_resource = []
        for slot in self:
            split_time = pytz.timezone(self._get_tz()).localize(departure_date).astimezone(pytz.utc).replace(tzinfo=None)
            if (slot.start_datetime < split_time) and (slot.end_datetime > split_time):
                shift_vals_list.append({
                    'start_datetime': split_time,
                    **slot._prepare_shift_vals(),
                })
                if split_time > slot.start_datetime:
                    slot.write({'end_datetime': split_time})
            elif slot.start_datetime >= split_time:
                shift_ids_to_remove_resource.append(slot.id)
        if shift_vals_list:
            self.sudo().create(shift_vals_list)
        if shift_ids_to_remove_resource:
            self.sudo().browse(shift_ids_to_remove_resource).write({'resource_id': False})

    def _group_expand_resource_id(self, resources, domain):
        dom_tuples = [(dom[0], dom[1]) for dom in domain if isinstance(dom, (tuple, list)) and len(dom) == 3]
        resource_ids = self.env.context.get('filter_resource_ids', False)
        if resource_ids:
            return self.env['resource.resource'].search([('id', 'in', resource_ids)])
        if self.env.context.get('planning_expand_resource') and ('start_datetime', '<') in dom_tuples and ('end_datetime', '>') in dom_tuples:
            # Search on the roles and resources
            search_on_role_domain = Domain.TRUE
            search_on_ressource_domain = Domain.TRUE
            if ('role_id', '=') in dom_tuples or ('role_id', 'ilike') in dom_tuples or ('role_id', 'in') in dom_tuples:
                role_search_domain = Domain(self._expand_domain_m2o_groupby(domain, 'role_id'))
                role_ids = self.env["planning.role"].search(role_search_domain).ids
                search_on_role_domain = Domain('role_ids', 'in', role_ids)
            if ('resource_id', '=') in dom_tuples or ('resource_id', 'ilike') in dom_tuples or ('resource_id', 'in') in dom_tuples:
                search_on_ressource_domain = Domain(self._expand_domain_m2o_groupby(domain, 'resource_id'))
            # Search on the slots
            filters = self._expand_domain_dates(domain)
            resources = self.env['planning.slot'].search(filters).mapped('resource_id')
            search_on_expanded_dates = Domain('id', 'in', resources.ids)
            # Merge the search domains
            if search_on_role_domain or search_on_ressource_domain:
                search_domain = search_on_role_domain & search_on_ressource_domain
                return self.env["resource.resource"].search(search_domain | search_on_expanded_dates)
            return self.env["resource.resource"].search(search_on_expanded_dates)
        return resources

    def _read_group_role_id(self, roles, domain):
        dom_tuples = [(dom[0], dom[1]) for dom in domain if isinstance(dom, list) and len(dom) == 3]
        if self.env.context.get('planning_expand_role') and ('start_datetime', '<') in dom_tuples and ('end_datetime', '>') in dom_tuples:
            if ('role_id', '=') in dom_tuples or ('role_id', 'ilike') in dom_tuples:
                filter_domain = self._expand_domain_m2o_groupby(domain, 'role_id')
                return self.env['planning.role'].search(filter_domain)
            filters = Domain.AND([[('role_id.active', '=', True)], self._expand_domain_dates(domain)])
            return self.env['planning.slot'].search(filters).mapped('role_id')
        return roles

    @api.model
    def _expand_domain_m2o_groupby(self, domain, filter_field=False):
        filter_domains = []
        for dom in domain:
            if dom[0] == filter_field:
                field = self._fields[dom[0]]
                if field.type == 'many2one' and len(dom) == 3:
                    if dom[1] in ['=', 'in']:
                        filter_domains.append([('id', dom[1], dom[2])])
                    elif dom[1] == 'ilike':
                        rec_name = self.env[field.comodel_name]._rec_name
                        filter_domains.append([(rec_name, dom[1], dom[2])])
        return Domain.OR(filter_domains) if filter_domains else Domain.TRUE

    def _expand_domain_dates(self, domain):
        delta = get_timedelta(1, self.env.context.get("scale", "week"))

        def update_start_end_dates(cond):
            if cond.field_expr == 'start_datetime' and cond.operator[0] == '<':
                value = cond.value or datetime.now()
                value += delta
            elif cond.field_expr == 'end_datetime' and cond.operator[0] == '>':
                value = cond.value or datetime.now()
                value -= delta
            else:
                return cond
            return Domain(cond.field_expr, cond.operator, value)

        return Domain(domain).optimize_full(self).map_conditions(update_start_end_dates)

    @api.model
    def _format_datetime_to_user_tz(self, datetime_without_tz, record_env, tz=None, lang_code=False):
        return format_datetime(record_env, datetime_without_tz, tz=tz, dt_format='short', lang_code=lang_code)

    def _send_slot(self, employee_ids, start_datetime, end_datetime, include_unassigned=True, message=None):
        if not include_unassigned:
            self = self.filtered(lambda s: s.resource_id)  # noqa: PLW0642
        if not self:
            return False
        self.ensure_one()

        employee_with_backend = employee_ids.filtered(lambda e: e.user_id)
        employee_without_backend = employee_ids - employee_with_backend
        planning = False
        employee_url_map = {}
        if employee_without_backend:
            planning = self.env['planning.planning'].create({
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'include_unassigned': include_unassigned,
            })
            employee_url_map = employee_without_backend.sudo()._planning_get_url(
                planning.date_start, planning.date_end, planning.access_token)

        template = self.env.ref('planning.email_template_slot_single')
        employee_url_map.update(employee_with_backend._planning_get_url(start_datetime.date(), end_datetime.date()))

        cal_url = self._get_slot_resource_urls()
        view_context = dict(self.env.context)
        view_context.update({
            'open_shift_available': not self.employee_id,
            'mail_subject': self.env._('Planning: new open shift available on'),
            'google_url': cal_url['google_url'],
            'iCal_url': cal_url['iCal'],
        })

        if self.employee_id:
            employee_ids = self.employee_id
            if self.allow_self_unassign and not self.is_unassign_deadline_passed:
                if employee_ids.filtered(lambda e: e.user_id):
                    unavailable_link = '/planning/unassign/%s/%s' % (self.employee_id.sudo().employee_token, self.id)
                else:
                    unavailable_link = '/planning/%s/%s/unassign/%s?message=1' % (planning.access_token, self.employee_id.sudo().employee_token, self.id)
                view_context.update({'unavailable_link': unavailable_link})
            view_context.update({'mail_subject': self.env._('Planning: new shift on')})

        mails_to_send_ids = []
        for employee in employee_ids.filtered(lambda e: e.work_email):
            if not self.employee_id and employee in employee_with_backend and not self.is_past:
                view_context.update({'available_link': '/planning/assign/%s/%s' % (employee.sudo().employee_token, self.id)})
            elif not self.employee_id and not self.is_past:
                view_context.update({'available_link': '/planning/%s/%s/assign/%s?message=1' % (planning.access_token, employee.sudo().employee_token, self.id)})
            start_datetime = self._format_datetime_to_user_tz(self.start_datetime, employee.env, tz=employee.tz, lang_code=employee.user_partner_id.lang)
            end_datetime = self._format_datetime_to_user_tz(self.end_datetime, employee.env, tz=employee.tz, lang_code=employee.user_partner_id.lang)
            unassign_deadline = self._format_datetime_to_user_tz(self.unassign_deadline, employee.env, tz=employee.tz, lang_code=employee.user_partner_id.lang)
            allocated_hours = timedelta(hours=self.allocated_hours).total_seconds()
            formatted_allocated_hours = "%d:%02d" % (allocated_hours // 3600, round(allocated_hours % 3600 / 60))
            allocated_percentage = float_utils.float_repr(self.allocated_percentage, precision_digits=0)
            # update context to build a link for view in the slot
            view_context.update({
                'link': employee_url_map[employee.id],
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'employee_name': employee.name,
                'work_email': employee.work_email,
                'allocated_hours': formatted_allocated_hours,
                'allocated_percentage': allocated_percentage,
                'unassign_deadline': unassign_deadline
            })
            mail_id = template.with_context(view_context).send_mail(self.id, email_layout_xmlid='mail.mail_notification_light')
            mails_to_send_ids.append(mail_id)

        mails_to_send = self.env['mail.mail'].sudo().browse(mails_to_send_ids)
        if mails_to_send:
            mails_to_send.send()

        self.write({
            'state': 'published',
            'publication_warning': False,
        })
        return None

    def _send_shift_assigned(self, slot, human_resource):
        email_from = slot.company_id.email or ''
        assignee = slot.resource_id.employee_id

        template = self.env.ref('planning.email_template_shift_switch_email', raise_if_not_found=False)
        start_datetime = self._format_datetime_to_user_tz(slot.start_datetime, assignee.env, tz=assignee.tz, lang_code=assignee.user_partner_id.lang)
        end_datetime = self._format_datetime_to_user_tz(slot.end_datetime, assignee.env, tz=assignee.tz, lang_code=assignee.user_partner_id.lang)
        allocated_hours = float_utils.float_repr(self.allocated_hours, precision_digits=2)
        allocated_percentage = float_utils.float_repr(self.allocated_percentage, precision_digits=0)
        template_context = {
            'old_assignee_name': assignee.name,
            'new_assignee_name': human_resource.employee_id.name,
            'start_datetime': start_datetime,
            'end_datetime': end_datetime,
            'allocated_hours': allocated_hours,
            'allocated_percentage': allocated_percentage,
        }
        if template and assignee != human_resource.employee_id:
            template.with_context(**template_context).send_mail(
                slot.id,
                email_values={
                    'email_to': assignee.work_email,
                    'email_from': email_from,
                },
                email_layout_xmlid='mail.mail_notification_light',
            )

    # ---------------------------------------------------
    # Slots generation/copy
    # ---------------------------------------------------

    @api.model
    def _merge_slots_values(self, slots_to_merge, unforecastable_intervals):
        """
            Return a list of merged slots

            - `slots_to_merge` is a sorted list of slots
            - `unforecastable_intervals` are the intervals where the employee cannot work

            Example:
                slots_to_merge = [{
                    'start_datetime': '2021-08-01 08:00:00',
                    'end_datetime': '2021-08-01 12:00:00',
                    'employee_id': 1,
                    'allocated_hours': 4.0,
                }, {
                    'start_datetime': '2021-08-01 13:00:00',
                    'end_datetime': '2021-08-01 17:00:00',
                    'employee_id': 1,
                    'allocated_hours': 4.0,
                }, {
                    'start_datetime': '2021-08-02 08:00:00',
                    'end_datetime': '2021-08-02 12:00:00',
                    'employee_id': 1,
                    'allocated_hours': 4.0,
                }, {
                    'start_datetime': '2021-08-03 08:00:00',
                    'end_datetime': '2021-08-03 12:00:00',
                    'employee_id': 1,
                    'allocated_hours': 4.0,
                }, {
                    'start_datetime': '2021-08-04 13:00:00',
                    'end_datetime': '2021-08-04 17:00:00',
                    'employee_id': 1,
                    'allocated_hours': 4.0,
                }]
                unforecastable = Intervals([(
                    datetime.datetime(2021, 8, 2, 13, 0, 0, tzinfo='UTC')',
                    datetime.datetime(2021, 8, 2, 17, 0, 0, tzinfo='UTC')',
                    self.env['resource.calendar.attendance'],
                )])

                result : [{
                    'start_datetime': '2021-08-01 08:00:00',
                    'end_datetime': '2021-08-02 12:00:00',
                    'employee_id': 1,
                    'allocated_hours': 12.0,
                }, {
                    'start_datetime': '2021-08-03 08:00:00',
                    'end_datetime': '2021-08-03 12:00:00',
                    'employee_id': 1,
                    'allocated_hours': 4.0,
                }, {
                    'start_datetime': '2021-08-04 13:00:00',
                    'end_datetime': '2021-08-04 17:00:00',
                    'employee_id': 1,
                    'allocated_hours': 4.0,
                }]

            :return list of merged slots
        """
        if not slots_to_merge:
            return slots_to_merge
        # resulting vals_list of the merged slots
        new_slots_vals_list = []
        # accumulator for mergeable slots
        sum_allocated_hours = 0
        to_merge = None
        # invariants for mergeable slots
        common_allocated_percentage = slots_to_merge[0]['allocated_percentage']
        resource_id = slots_to_merge[0].get('resource_id')
        start_datetime = slots_to_merge[0]['start_datetime']
        previous_end_datetime = start_datetime
        for slot in slots_to_merge:
            mergeable = True
            if (not slot['start_datetime']
               or common_allocated_percentage != slot['allocated_percentage']
               or resource_id != slot['resource_id']
               or (slot['start_datetime'] - previous_end_datetime).total_seconds() > 3600 * 24):
                # last condition means the elapsed time between the previous end time and the
                # start datetime of the current slot should not be bigger than 24hours
                # if it's the case, then the slot can not be merged.
                mergeable = False
            if mergeable:
                end_datetime = slot['end_datetime']
                interval = Intervals([(
                    pytz.utc.localize(start_datetime),
                    pytz.utc.localize(end_datetime),
                    self.env['resource.calendar.attendance']
                )])
                if not (interval & unforecastable_intervals):
                    sum_allocated_hours += slot['allocated_hours']
                    to_merge = {
                        **slot,
                        'start_datetime': start_datetime,
                        'allocated_hours': sum_allocated_hours,
                    }
                else:
                    mergeable = False
            if not mergeable:
                if to_merge:
                    new_slots_vals_list.append(to_merge)
                to_merge = slot
                start_datetime = slot['start_datetime']
                common_allocated_percentage = slot['allocated_percentage']
                resource_id = slot.get('resource_id')
                sum_allocated_hours = slot['allocated_hours']
            previous_end_datetime = slot['end_datetime']
        if to_merge:
            new_slots_vals_list.append(to_merge)
        return new_slots_vals_list

    def _get_working_hours_over_period(self, start_utc, end_utc, work_intervals, calendar_intervals, flexible_resources_hours_per_day=None, flexible_resources_hours_per_week=None):
        """
        Compute the total work hours of the slot based on its work intervals or its working calendar.
        The following are the different cases:
        1) If the assigned resource has a flexible contract, its working hours is computed via _get_flexible_resource_work_hours
           that takes into account contract, timeoff, max hours per day and per week
        3) If the slot is an open shift, take the `hours_per_day` of the company's calendar to calculate the working hours.
           this allows the creation of open slots outside the company's calendar attendance (such as weekends).
        4) If the resource is assigned and has fixed working hours, compute the work hours based on its work intervals.
        """
        start = max(start_utc, pytz.utc.localize(self.start_datetime))
        end = min(end_utc, pytz.utc.localize(self.end_datetime))
        slot_interval = Intervals([(
            start, end, self.env['resource.calendar.attendance']
        )])

        if self.resource_id and self.resource_id._is_flexible():
            assert flexible_resources_hours_per_day is not None and flexible_resources_hours_per_week is not None
            return self.resource_id._get_flexible_resource_work_hours(slot_interval & work_intervals[self.resource_id.id], flexible_resources_hours_per_day.get(self.resource_id.id, 0.0), flexible_resources_hours_per_week.get(self.resource_id.id, 0.0))

        period = self.end_datetime - self.start_datetime
        slot_duration = period.total_seconds() / 3600
        # For open shift, take the `hours_per_day` of the company's default calendar
        if not self.resource_id and self.allocation_type == 'forecast':
            max_hours_per_day = self.company_id.resource_calendar_id.hours_per_day
            max_duration = (period.days + (1 if period.seconds else 0)) * max_hours_per_day
            return round(min(slot_duration, max_duration), 2)

        # Resource with fixed working hours, else we refer to the company's calendar
        working_intervals = work_intervals[self.resource_id.id] \
            if self.resource_id \
            else calendar_intervals[self.company_id.resource_calendar_id.id]
        return round(sum_intervals(slot_interval & working_intervals), 2)

    def _get_slot_resource_urls(self):
        def get_url_dt(dt):
            return dt.astimezone(pytz.timezone(self._get_tz())).strftime('%Y%m%dT%H%M%S')
        ics_description_data = {
            'shift': self._get_ics_description_data(),
            'is_google_url': True,
        }
        return {
            'google_url': "https://www.google.com/calendar/render?" + url_encode({
                'action': 'TEMPLATE',
                'text': self.display_name or self.env._('New Shift'),  # Event title
                'dates': f'{get_url_dt(self.start_datetime)}/{get_url_dt(self.end_datetime)}',  # Event start and end date/time
                'ctz': self._get_tz(),
                'details': self.env['ir.qweb']._render('planning.planning_shift_ics_description', ics_description_data),
            }),
            'iCal': f'/slot/{self.access_token}.ics',
        }

    def _get_duration_over_period(self, start_utc, stop_utc, work_intervals, calendar_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week, has_allocated_hours=True):
        assert start_utc.tzinfo and stop_utc.tzinfo
        self.ensure_one()
        start, stop = start_utc.replace(tzinfo=None), stop_utc.replace(tzinfo=None)
        if has_allocated_hours and self.start_datetime >= start and self.end_datetime <= stop:
            return self.allocated_hours
        # if the slot goes over the gantt period, compute the duration only within the gantt period
        ratio = self.allocated_percentage / 100.0
        working_hours = self._get_working_hours_over_period(start_utc, stop_utc, work_intervals, calendar_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week)
        return working_hours * ratio

    def _get_employee_work_hours_within_interval(self, resource, work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week):
        """
        Compute the total work hours of the employee based on its work intervals or its calendar flexible hours.
        :param work_intervals: a dictionary {work_entry_id: hours_1, work_entry_2: hours_2}
        :return: the number of work hours

        This covers 2 user cases:
        1) If the employee has a flexible contract, its working hours is computed via _get_flexible_resource_work_hours
           that takes into account contract, timeoff, max hours per day and per week
        2) if the employee has a fixed working hours, we compute the work hours based on its work intervals.
        """
        if resource._is_flexible():
            return resource._get_flexible_resource_work_hours(work_intervals, flexible_resources_hours_per_day[resource.id], flexible_resources_hours_per_week[resource.id])

        return sum_intervals(work_intervals)

    def _gantt_progress_bar_resource_id(self, res_ids, start, stop):
        start_naive, stop_naive = start.replace(tzinfo=None), stop.replace(tzinfo=None)

        resources = self.env['resource.resource'].with_context(active_test=False).search([('id', 'in', res_ids)])
        planning_slots = self.env['planning.slot'].search([
            ('resource_id', 'in', res_ids),
            ('start_datetime', '<=', stop_naive),
            ('end_datetime', '>=', start_naive),
        ])

        flexible_resources = resources.filtered(lambda r: r._is_flexible())
        regular_resources = resources - flexible_resources

        planned_hours_mapped = defaultdict(float)
        resource_work_intervals, calendar_work_intervals = regular_resources.sudo()._get_valid_work_intervals(start, stop)

        flexible_resource_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week = flexible_resources._get_flexible_resource_valid_work_intervals(start, stop)
        resource_work_intervals.update(flexible_resource_work_intervals)

        for slot in planning_slots:
            planned_hours_mapped[slot.resource_id.id] += slot._get_duration_over_period(
                start, stop, resource_work_intervals, calendar_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week
            )
        # Compute employee work hours based on its work intervals or flexible hours.
        work_hours = {}
        for resource_id, work_intervals in resource_work_intervals.items():
            resource = resources.browse(resource_id)
            work_hours[resource_id] = self._get_employee_work_hours_within_interval(resource, work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week)

        company_calendar = self.env.company.resource_calendar_id
        # Export work intervals in UTC
        resource_work_intervals[False] = (
            calendar_work_intervals.get(company_calendar.id)
            or company_calendar._work_intervals_batch(start, stop)[False]
        )
        work_interval_per_resource = defaultdict(list)
        for resource_id, resource_work_intervals_per_resource in resource_work_intervals.items():
            for resource_work_interval in resource_work_intervals_per_resource:
                work_interval_per_resource[resource_id].append(
                    (resource_work_interval[0].replace(tzinfo=pytz.UTC), resource_work_interval[1].replace(tzinfo=pytz.UTC))
                )
        # Add average daily work hours per resource calendar to the output
        avg_hours_per_resource = {False: 0}
        for resource in set(resources):
            if resource._is_fully_flexible():
                avg_hours_per_resource[resource.id] = 24    # set to 24 hours if the resource is fully flexible
            else:
                avg_hours_per_resource[resource.id] = (resource.calendar_id or company_calendar).hours_per_day

        return {
            resource.id: {
                'is_material_resource': resource.resource_type == 'material',
                'resource_color': resource.color,
                'display_popover_material_resource': len(resource.role_ids) > 1,
                'value': planned_hours_mapped[resource.id],
                'max_value': work_hours.get(resource.id, 0.0),
                'employee_id': resource.employee_id.id,
                'is_flexible_hours': resource._is_flexible(),
                'is_fully_flexible_hours': resource._is_fully_flexible(),
                'work_intervals': work_interval_per_resource.get(resource.id, 0.0),
                'avg_hours': avg_hours_per_resource.get(resource.id, 0.0),
            }
            for resource in resources
        }

    def _gantt_progress_bar(self, field, res_ids, start, stop):
        if not self.env.user._is_internal():
            return {}
        if field == 'resource_id':
            start, stop = pytz.utc.localize(start), pytz.utc.localize(stop)
            return dict(
                self._gantt_progress_bar_resource_id(res_ids, start, stop),
                warning=self.env._("This employee is not expected to work during this period, either because they do not have a current contract or because they are on leave.")
            )
        raise NotImplementedError(self.env._("This Progress Bar is not implemented."))

    def _prepare_shift_vals(self):
        """ Generate shift vals"""
        self.ensure_one()
        return {
            'resource_id': False,
            'end_datetime': self.end_datetime,
            'role_id': self.role_id.id,
            'company_id': self.company_id.id,
            'allocated_percentage': self.allocated_percentage,
            'name': self.name,
            'recurrency_id': self.recurrency_id.id,
            'repeat': self.repeat,
            'repeat_interval': self.repeat_interval,
            'repeat_unit': self.repeat_unit,
            'repeat_type': self.repeat_type,
            'repeat_until': self.repeat_until,
            'repeat_number': self.repeat_number,
            'template_id': self.template_id.id,
        }

    def undo_split_shift(self, start_datetime, end_datetime, resource_id):
        if len(self) != 2:
            raise ValueError(self.env._("This method must take two slots in argument."))
        initial_shift, copied_shift = self
        if not (initial_shift.exists() and copied_shift.exists()):
            return False
        initial_shift.start_datetime = start_datetime
        initial_shift.end_datetime = end_datetime
        initial_shift.resource_id = resource_id
        copied_shift.unlink()
        return True

    @api.model
    def _gantt_resource_employees_working_periods(self, groups, start_date, stop_date):
        if not self.env.user.has_group('planning.group_planning_manager'):
            return {}

        resource_ids = {group["resource_id"][0] for group in groups if group["resource_id"]}

        employee_ids = set()
        employee_id_to_ressource_id = {}
        working_periods = {}
        for resource in self.env["resource.resource"].browse(resource_ids):
            if not resource.employee_id:
                continue
            resource_id = resource.id
            employee_id = resource.employee_id.id
            employee_ids.add(employee_id)
            employee_id_to_ressource_id[employee_id] = resource_id
            working_periods[resource_id] = []

        if employee_ids:
            start, stop = fields.Datetime.from_string(start_date), fields.Datetime.from_string(stop_date)

            employees_sudo = self.env["hr.employee"].sudo().browse(employee_ids)
            employees_with_contract = dict(
                self.env["hr.version"].sudo()._read_group(
                    domain=[
                        ("employee_id", "in", employees_sudo.ids),
                        ('contract_date_start', '!=', False),
                    ],
                    groupby=["employee_id"],
                    aggregates=["__count"],
                )
            )
            contracts = employees_sudo._get_versions_with_contract_overlap_with_period(start.date(), stop.date())
            employees_with_contract_in_current_scale = []
            for contract in contracts:
                employee_id = contract.employee_id.id
                end_datetime = contract.contract_date_end and contract.contract_date_end + relativedelta(hour=23, minute=59, second=59)
                if end_datetime:
                    user_tz = pytz.timezone(self.env.user.tz or self.env.context.get('tz') or 'UTC')
                    end_datetime = user_tz.localize(end_datetime).astimezone(pytz.utc).replace(tzinfo=None)
                    end_datetime = fields.Datetime.to_string(end_datetime)
                employees_with_contract_in_current_scale.append(employee_id)
                working_periods[employee_id_to_ressource_id[employee_id]].append({
                    "start": fields.Datetime.to_string(contract.contract_date_start),
                    "end": end_datetime,
                })
            for employee in employees_sudo - self.env["hr.employee"].browse(employees_with_contract_in_current_scale):
                if employees_with_contract.get(employee):
                    continue
                working_periods[employee_id_to_ressource_id[employee.id]].append({
                    "start": start_date,
                    "end": stop_date,
                })
        return working_periods
