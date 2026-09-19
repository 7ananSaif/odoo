# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from functools import partial
import pytz

from odoo import api, fields, models, Command, _
from odoo.tools.date_utils import localized, to_timezone
from odoo.tools.intervals import Intervals
from odoo.exceptions import UserError


class MaintenanceStage(models.Model):
    _inherit = 'maintenance.stage'

    create_leaves = fields.Boolean('Request Confirmed', default=True,
        help="When this box is unticked, and the maintenance is of the type 'Work Center', no leave is created on the respective work center when a maintenance request is created.\n"
            "If the box is ticked, the work center is automatically blocked for the listed duration, either at the specified date, or as soon as possible, if the work center is unavailable then.")

    def write(self, vals):
        res = super().write(vals)
        if 'create_leaves' in vals:
            maintenance_requests = self.env['maintenance.request'].search([('maintenance_for', '=', 'workcenter'), ('stage_id', 'in', self.ids)])
            maintenance_requests._recreate_leaves()
        return res


class MrpWorkcenter(models.Model):
    _name = 'mrp.workcenter'
    _inherit = ["mrp.workcenter", 'maintenance.mixin', 'mail.thread', 'mail.activity.mixin']

    equipment_ids = fields.One2many(
        'maintenance.equipment', 'workcenter_id', string="Maintenance Equipment",
        check_company=True)
    maintenance_ids = fields.One2many('maintenance.request', 'workcenter_id', domain=[('maintenance_for', '=', 'workcenter')])

    def _get_unavailability_intervals(self, start_datetime, end_datetime):
        res = super(MrpWorkcenter, self)._get_unavailability_intervals(start_datetime, end_datetime)
        if not self:
            return res
        sql = """
          SELECT workcenter_id, ARRAY_AGG(ARRAY[schedule_date, schedule_end]) as date_intervals
            FROM maintenance_request
           WHERE maintenance_for = 'equipment'
             AND schedule_date IS NOT NULL
             AND schedule_end IS NOT NULL
             AND workcenter_id IN %s
             AND (schedule_date, schedule_end) OVERLAPS (%s, %s)
        GROUP BY workcenter_id
        """
        self.env.cr.execute(sql, [tuple(self.ids), fields.Datetime.to_string(start_datetime.astimezone()), fields.Datetime.to_string(end_datetime.astimezone())])
        res_maintenance = defaultdict(list)
        for wc_row in self.env.cr.dictfetchall():
            res_maintenance[wc_row.get('workcenter_id')] = wc_row.get('date_intervals')

        for wc_id in self.ids:
            intervals_previous_list = [(s.timestamp(), e.timestamp(), self.env['maintenance.request']) for s, e in res[wc_id]]
            intervals_maintenances_list = [(m[0].timestamp(), m[1].timestamp(), self.env['maintenance.request']) for m in res_maintenance[wc_id]]
            final_intervals_wc = Intervals(intervals_previous_list + intervals_maintenances_list)
            res[wc_id] = [(datetime.fromtimestamp(s), datetime.fromtimestamp(e)) for s, e, _ in final_intervals_wc]
        return res

    def _get_first_flexible_available_slot(self, start_datetime, duration) -> tuple[datetime | None, datetime | None]:
        """
        Get the first available interval for the workcenter, ignoring working schedule (flexible).

        Returns the first available interval within 700 days of the requested start date, or (None, None) if none is found.

        :param start_datetime: datetime to start searching from
        :param duration: required duration of the slot (in hours)
        :return: tuple containing (start datetime, end datetime) or (None, None)
        """
        self.ensure_one()
        resource = self.resource_id
        calendar_tz = pytz.timezone(self.resource_calendar_id.tz)
        revert = to_timezone(start_datetime.tzinfo)
        start_datetime = localized(start_datetime)
        get_workorder_intervals = partial(
            self.resource_calendar_id._leave_intervals_batch,
            domain=[('time_type', '=', 'other')],  # workorder leaves only
            resources=resource,
            tz=calendar_tz,
        )

        date_start = start_datetime
        duration = relativedelta(hours=duration)
        result = None, None
        date_limit = start_datetime + relativedelta(days=700)  # Limit search to 700 days to ensure performance.
        while date_start <= date_limit:
            date_end = date_start + duration

            if not (workorder_intervals := get_workorder_intervals(date_start, date_end)[resource.id]):
                result = revert(date_start), revert(date_end)  # if no overlapping intervals found
                break
            # Set next start to the original end date of the last leave interval (not the clipped overlap)
            date_start = localized(max(list(workorder_intervals)[-1][2].mapped('date_to')))
        return result


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"
    _check_company_auto = True

    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Work Center', check_company=True, index='btree_not_null')

    def button_mrp_workcenter(self):
        self.ensure_one()
        return {
            'name': _('work centers'),
            'view_mode': 'form',
            'res_model': 'mrp.workcenter',
            'view_id': self.env.ref('mrp.mrp_workcenter_view').id,
            'type': 'ir.actions.act_window',
            'res_id': self.workcenter_id.id,
            'context': {
                'default_company_id': self.company_id.id
            }
        }


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"
    _check_company_auto = True

    production_id = fields.Many2one(
        'mrp.production', string='Manufacturing Order', check_company=True, index='btree_not_null')
    workorder_id = fields.Many2one(
        'mrp.workorder', string='Work Order', check_company=True)
    production_company_id = fields.Many2one(string='Production Company', related='production_id.company_id')
    company_id = fields.Many2one(domain="[('id', '=?', production_company_id)]")
    maintenance_for = fields.Selection([
        ('equipment', 'Equipment'),
        ('workcenter', 'Work Center')],
        string='For', default='equipment', required=True)
    equipment_id = fields.Many2one(compute='_compute_equipment_id', store=True, readonly=False)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Center', compute='_compute_workcenter_id', store=True, readonly=False, check_company=True, index='btree_not_null')
    block_workcenter = fields.Boolean('Block Workcenter', help="It won't be possible to plan work orders or other maintenances on this workcenter during this time.")
    recurring_leaves_count = fields.Integer('Additional Leaves to Plan Ahead', help='Block the workcenter for this many time slots in the future in advance.')
    leave_ids = fields.Many2many('resource.calendar.leaves', string="Leaves")

    @api.depends('maintenance_for')
    def _compute_equipment_id(self):
        self.filtered(lambda mr: mr.maintenance_for == 'workcenter' and mr.equipment_id).equipment_id = False

    @api.depends('maintenance_for', 'equipment_id')
    def _compute_workcenter_id(self):
        for request in self:
            if request.maintenance_for == 'equipment':
                request.workcenter_id = request.equipment_id.workcenter_id

    @api.depends('workcenter_id')
    def _compute_maintenance_team_id(self):
        for request in self:
            if request.workcenter_id and request.workcenter_id.maintenance_team_id:
                request.maintenance_team_id = request.workcenter_id.maintenance_team_id
        return super()._compute_maintenance_team_id()

    @api.depends('workcenter_id')
    def _compute_user_id(self):
        for request in self:
            if request.maintenance_for == 'workcenter':
                request.user_id = request.workcenter_id.technician_user_id
        return super()._compute_user_id()

    @api.model_create_multi
    def create(self, vals_list):
        allowed_to_raise = not self.id  # self.copy() has an id, model.create() does not
        res = super().create(vals_list)
        res._recreate_leaves(raise_on_schedule_date_already_planned=allowed_to_raise)  # do not raise when copying recurrent request
        return res

    def write(self, vals):
        previous_create_leaves = {request.id: request.stage_id.create_leaves for request in self}
        res = super().write(vals)
        if 'leave_ids' not in vals and any(k in vals for k in ['workcenter_id', 'schedule_date', 'schedule_end',
                                                               'maintenance_type',
                                                               'recurring_maintenance',
                                                               'repeat_interval', 'repeat_unit', 'repeat_type', 'repeat_until',
                                                               'block_workcenter',
                                                               'recurring_leaves_count']):
            self._recreate_leaves()
        elif 'stage_id' in vals:
            self.filtered(lambda mr: mr.stage_id.create_leaves != previous_create_leaves[mr.id])._recreate_leaves()
        return res

    def unlink(self):
        self.leave_ids.unlink()
        return super().unlink()

    def _need_new_activity(self, vals):
        return super()._need_new_activity(vals) or vals.get('workcenter_id')

    def _get_activity_note(self):
        self.ensure_one()
        if self.maintenance_for == 'workcenter':
            return _(
                'Request planned for %s',
                self.workcenter_id._get_html_link()
            )
        return super()._get_activity_note()

    def _recreate_leaves(self, raise_on_schedule_date_already_planned=True):
        """Allocate a new leave (and the early preventive ones) for the maintenance
        based on schedule date and duration.
        """
        self.leave_ids.unlink()
        for request in self:
            if request.archive:
                continue
            if request.maintenance_for != 'workcenter':
                continue
            if not request.schedule_date:
                continue
            if not request.workcenter_id:
                raise UserError(_("The workcenter is missing for %s.", request.display_name))
            if not request.block_workcenter:
                continue
            if request.stage_id.done or not request.stage_id.create_leaves:
                continue
            desired_date = request.schedule_date
            duration = request.duration or 1

            # Use '_get_first_flexible_available_slot' to find the first flexible available slot as maintenance can be
            # scheduled at a non working hours unlike work orders.
            if desired_date != request.workcenter_id._get_first_flexible_available_slot(desired_date, duration)[0] \
                and raise_on_schedule_date_already_planned:
                raise UserError(self.env._("Manufacturing Orders are already scheduled for this time slot."))

            count = 1
            if request.maintenance_type == 'preventive' and request.recurring_maintenance:
                count += request.recurring_leaves_count
            date = desired_date
            leave_ids_vals = []
            text = ""
            for _i in range(count):
                from_date, to_date = request.workcenter_id._get_first_flexible_available_slot(date, duration)
                if not from_date or not to_date:
                    text = self.env._("No available slot within 700 days after the planned start.")
                    break
                leave_ids_vals.append(Command.create({
                    'name': request.display_name,
                    'resource_id': request.workcenter_id.resource_id.id,
                    'calendar_id': request.workcenter_id.resource_calendar_id.id,
                    'date_from': from_date,
                    'date_to': to_date,
                    'time_type': 'leave',
                }))
                date += relativedelta(**{f"{request.repeat_unit}s": request.repeat_interval})
                if request.repeat_type == 'until' and date.date() > request.repeat_until:
                    break
            effective_date = leave_ids_vals and leave_ids_vals[0][2]['date_from']
            date_to = leave_ids_vals and leave_ids_vals[0][2]['date_to']
            request.write({
                'schedule_date': effective_date,
                'schedule_end': date_to,
                'leave_ids': leave_ids_vals,
            })
            if effective_date != desired_date:
                user_tz = self.env.user.tz or self.env.context.get('tz')
                user_pytz = pytz.timezone(user_tz) if user_tz else pytz.utc
                text = text or self.env._("The schedule has changed from %(desired_date)s to %(effective_date)s due to planned manufacturing orders.", desired_date=desired_date.astimezone(user_pytz), effective_date=effective_date.astimezone(user_pytz))
                self.activity_schedule(
                    'mail.mail_activity_data_warning',
                    note=text,
                    user_id=self.env.uid,
                )

    def archive_equipment_request(self):
        res = super().archive_equipment_request()
        self.leave_ids.unlink()
        self.write({'block_workcenter': False, 'recurring_leaves_count': 0})
        return res


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    maintenance_count = fields.Integer(compute='_compute_maintenance_count', string="Number of maintenance requests")
    request_ids = fields.One2many('maintenance.request', 'production_id')

    @api.depends('request_ids')
    def _compute_maintenance_count(self):
        for production in self:
            production.maintenance_count = len(production.request_ids)

    def button_maintenance_req(self):
        self.ensure_one()
        return {
            'name': _('New Maintenance Request'),
            'view_mode': 'form',
            'res_model': 'maintenance.request',
            'type': 'ir.actions.act_window',
            'context': {
                'default_company_id': self.company_id.id,
                'default_production_id': self.id,
            },
            'domain': [('production_id', '=', self.id)],
        }

    def open_maintenance_request_mo(self):
        self.ensure_one()
        action = {
            'name': _('Maintenance Requests'),
            'view_mode': 'kanban,list,form,pivot,graph,calendar',
            'res_model': 'maintenance.request',
            'type': 'ir.actions.act_window',
            'context': {
                'default_company_id': self.company_id.id,
                'default_production_id': self.id,
            },
            'domain': [('production_id', '=', self.id)],
        }
        if self.maintenance_count == 1:
            production = self.env['maintenance.request'].search([('production_id', '=', self.id)])
            action['view_mode'] = 'form'
            action['res_id'] = production.id
        return action


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def button_maintenance_req(self):
        self.ensure_one()
        return {
            'name': _('New Maintenance Request'),
            'view_mode': 'form',
            'views': [(self.env.ref('mrp_maintenance.maintenance_request_view_form_inherit_mrp_workorder').id, 'form')],
            'res_model': 'maintenance.request',
            'type': 'ir.actions.act_window',
            'context': {
                'default_company_id': self.company_id.id,
                'default_workorder_id': self.id,
                'default_production_id': self.production_id.id,
                'discard_on_footer_button': True,
            },
            'target': 'new',
            'domain': [('workorder_id', '=', self.id)]
        }
