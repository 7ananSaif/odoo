from datetime import timezone
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    l10n_be_sickness_relapse = fields.Boolean(default=True, string="Sickness Relapse")
    l10n_be_sickness_can_relapse = fields.Boolean(compute="_compute_can_relapse")

    @api.depends("date_from", "validation_type", "employee_id", "holiday_status_id.work_entry_type_id.code")
    def _compute_can_relapse(self):
        l10n_be_leaves = self.filtered(
            lambda leave:
            leave.company_id.country_code == "BE"
            and leave.validation_type == "hr"
            and leave.employee_id
            and leave.date_from
        )

        sick_work_entry_type = self.env.ref("hr_work_entry.work_entry_type_sick_leave")
        partial_sick_work_entry_type = self.env.ref("hr_work_entry.l10n_be_work_entry_type_part_sick")
        long_sick_work_entry_type = self.env.ref("hr_work_entry.l10n_be_work_entry_type_long_sick")
        sick_work_entry_types = (
            sick_work_entry_type
            + partial_sick_work_entry_type
            + long_sick_work_entry_type
        )

        if l10n_be_leaves:
            recent_leaves = dict(
                    self
                    .env["hr.leave"]
                    ._read_group(
                        domain=[
                            ("employee_id.id", "in", l10n_be_leaves.employee_id.ids),
                            ("date_to", "<=", max(l10n_be_leaves.mapped("date_from"))),
                            ("date_to", ">=", min(l10n_be_leaves.mapped(lambda l: l.date_from + relativedelta(days=-14)))),
                            ("holiday_status_id.work_entry_type_id", "in", sick_work_entry_types.ids),
                            ("state", "=", "validate"),
                        ],
                        groupby=["employee_id"],
                        aggregates=["request_date_to:max"],
                    )
            )
            for employee, leaves in l10n_be_leaves.grouped('employee_id').items():
                for leave in leaves:
                    leave.l10n_be_sickness_can_relapse = bool(recent_leaves.get(employee))

        for leave in (self - l10n_be_leaves):
            leave.l10n_be_sickness_can_relapse = False

    def _action_validate(self, check_state=True):
        res = super()._action_validate(check_state=check_state)
        activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
        res_model_id = self.env.ref('hr_holidays.model_hr_leave').id
        for leave in self:
            leave._check_consecutive_leaves()
            if leave.employee_id.company_id.country_id.code == "BE" and \
                    leave.sudo().holiday_status_id.work_entry_type_id.code in self._get_drs_work_entry_type_codes():
                drs_link = "https://www.socialsecurity.be/site_fr/employer/applics/drs/index.htm"
                drs_link = '<a href="%s" target="_blank">%s</a>' % (drs_link, drs_link)
                user_ids = leave.holiday_status_id.responsible_ids.ids
                note = _('%(employee)s is in %(holiday_status)s. Fill in the appropriate eDRS here: %(link)s',
                   employee=leave.employee_id.name,
                   holiday_status=leave.holiday_status_id.name,
                   link=drs_link)
                activity_vals = []
                for user_id in user_ids:
                    activity_vals.append({
                        'activity_type_id': activity_type_id,
                        'automated': True,
                        'note': note,
                        'user_id': user_id,
                        'res_id': leave.id,
                        'res_model_id': res_model_id,
                    })
                # TDE TODO: batch schedule with record-based note
                self.env['mail.activity'].create(activity_vals)
        return res

    def _get_drs_work_entry_type_codes(self):
        drs_work_entry_types = [
            'LEAVE290', # Breast Feeding
            'LEAVE280', # Long Term Sick
            'LEAVE210', # Maternity
            'LEAVE230', # Paternity Time Off (Legal)
            'YOUNG01',  # Youth Time Off
            'LEAVE115', # Work Accident
        ]
        return drs_work_entry_types

    def _check_work_interval_between_dates(self, date_from, date_to, employee):
        '''
        Check if there is a work interval between two dates for an employee
        Returns true if there is a period where the employee worked 
        or had a leave borne by the employee (e.g. not a public holiday)
        between date_from and date_to
        '''
        calendar = employee._get_calendars()[employee.id]
        dt_from = date_from.replace(tzinfo=timezone.utc)
        dt_to = date_to.replace(tzinfo=timezone.utc)
        attendance_intervals = calendar._attendance_intervals_batch(dt_from, dt_to, employee.resource_id)
        leave_intervals = calendar._leave_intervals_batch(dt_from, dt_to, employee.resource_id)
        employee_leave_intervals = leave_intervals[employee.resource_id.id]
        # remove holidays taken by the user from employee_leave_intervals
        employee_leave_intervals -= [
            (start, end, leave)
            for start, end, leave in employee_leave_intervals
            if leave.holiday_id
        ]
        attendance_intervals = attendance_intervals[employee.resource_id.id] - employee_leave_intervals
        return bool(attendance_intervals)

    def _check_consecutive_leaves(self):
        self.ensure_one()
        if not self.holiday_status_id.l10n_be_no_consecutive_leaves_allowed:
            return
        employee = self.employee_id
        last_leave_taken = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('date_to', '<', self.date_from),
            ('holiday_status_id', '=', self.holiday_status_id.id),
            ('state', '=', 'validate'),
        ], order='date_to desc', limit=1)
        next_leave_taken = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('date_from', '>', self.date_to),
            ('holiday_status_id', '=', self.holiday_status_id.id),
            ('state', '=', 'validate'),
        ], order='date_from asc', limit=1)
        if last_leave_taken:
            if not self._check_work_interval_between_dates(last_leave_taken.date_to, self.date_from, employee):
                raise UserError(_("You can't take two consecutive leaves of the same type."))
        if next_leave_taken:
            if not self._check_work_interval_between_dates(self.date_to, next_leave_taken.date_from, employee):
                raise UserError(_("You can't take two consecutive leaves of the same type."))
