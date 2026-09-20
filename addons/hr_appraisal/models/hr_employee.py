# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    next_appraisal_date = fields.Date(
        string='Next Appraisal Date', compute='_compute_next_appraisal_date', groups="hr.group_hr_user", readonly=False, store=True, copy=False,
        help="The date of the next appraisal is computed by the appraisal plan's dates (first appraisal + periodicity).")
    last_ongoing_appraisal_date = fields.Date(compute='_compute_last_ongoing_appraisal_date', groups="hr.group_hr_user")
    is_last_appraisal_late = fields.Boolean(compute='_compute_last_ongoing_appraisal_date', groups="hr.group_hr_user")
    related_partner_id = fields.Many2one('res.partner', compute='_compute_related_partner', groups="hr.group_hr_user")
    ongoing_appraisal_count = fields.Integer(compute='_compute_ongoing_appraisal_count', store=True)
    appraisal_count = fields.Integer(compute='_compute_appraisal_count', store=True, groups="hr.group_hr_user")
    uncomplete_goals_count = fields.Integer(compute='_compute_uncomplete_goals_count', groups="hr.group_hr_user")
    goals_count = fields.Integer(compute='_compute_goals_count', groups="hr.group_hr_user")
    appraisal_ids = fields.One2many('hr.appraisal', 'employee_id', groups="hr.group_hr_user")
    can_request_appraisal = fields.Boolean(compute='_compute_can_request_appraisal')
    goals_ids = fields.Many2many(
        'hr.appraisal.goal', 'hr_appraisal_goal_hr_employee_rel', 'hr_employee_id',
        string="Goals", groups="hr.group_hr_user")
    parent_user_id = fields.Many2one(related='parent_id.user_id', string="Parent User")
    last_appraisal_id = fields.Many2one('hr.appraisal')
    last_appraisal_state = fields.Selection(related='last_appraisal_id.state')

    def _get_appraisal_plan_starting_date(self):
        self.ensure_one()
        return self.create_date

    def action_send_appraisal_request(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.appraisal',
            'name': 'Appraisal Request',
            'context': self.env.context,
        }

    def action_open_last_appraisal(self):
        self.ensure_one()
        employee_appraisals = self.with_context(active_test=False).appraisal_ids
        opened_appraisals = employee_appraisals.filtered(lambda a: a.state in ['1_new', '2_pending'])
        done_appraisals = employee_appraisals.filtered(lambda a: a.state == '3_done')
        relevant_appraisals = employee_appraisals
        if opened_appraisals:
            relevant_appraisals = opened_appraisals
        elif done_appraisals:
            relevant_appraisals = done_appraisals[0]
        if len(relevant_appraisals) == 1:
            return {
                'view_mode': 'form',
                'res_model': 'hr.appraisal',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': relevant_appraisals.id,
            }
        else:
            return {
                'view_mode': 'list',
                'name': self.env._('New and Pending Appraisals'),
                'res_model': 'hr.appraisal',
                "views": [[self.env.ref('hr_appraisal.view_hr_appraisal_tree').id, "list"], [False, "form"]],
                'type': 'ir.actions.act_window',
                'target': 'current',
                'domain': [('id', 'in', relevant_appraisals.ids)],
            }

    def _compute_can_request_appraisal(self):
        children_ids = self.env.user.get_employee_autocomplete_ids().ids
        for employee in self.sudo():
            # Since this function is used in both private and public employees, to check if an employee is in the list
            # we need to check by their id, which is the same in corresponding private and public employees.
            employee.can_request_appraisal = employee.id in children_ids

    @api.constrains('next_appraisal_date')
    def _check_next_appraisal_date(self):
        today = fields.Date.today()
        if not self.env.context.get('install_mode') and any(employee.next_appraisal_date and employee.next_appraisal_date < today for employee in self):
            raise ValidationError(self.env._("You cannot set 'Next Appraisal Date' in the past."))

    def _compute_related_partner(self):
        for rec in self:
            rec.related_partner_id = rec.user_id.partner_id or rec.work_contact_id

    @api.depends('appraisal_ids')
    def _compute_appraisal_count(self):
        read_group_result = self.env['hr.appraisal'].with_context(active_test=False)._read_group([('employee_id', 'in', self.ids)], ['employee_id'], ['__count'])
        result = {employee.id: count for employee, count in read_group_result}
        for employee in self:
            employee.appraisal_count = result.get(employee.id, 0)

    @api.depends('appraisal_ids.state')
    def _compute_ongoing_appraisal_count(self):
        read_group_result = self.env['hr.appraisal'].with_context(active_test=False)._read_group([('employee_id', 'in', self.ids), ('state', 'in', ['1_new', '2_pending'])], ['employee_id'], ['__count'])
        result = {employee.id: count for employee, count in read_group_result}
        for employee in self:
            employee.ongoing_appraisal_count = result.get(employee.id, 0)

    def _compute_uncomplete_goals_count(self):
        read_group_result = self.env['hr.appraisal.goal']._read_group([('employee_ids', 'in', self.ids), ('progression', '!=', '100'), ('child_ids', '=', False)], ['employee_ids'], ['__count'])
        result = {employee.id: count for employee, count in read_group_result}
        for employee in self:
            employee.uncomplete_goals_count = result.get(employee.id, 0)

    def _compute_goals_count(self):
        read_group_result = self.env['hr.appraisal.goal']._read_group([('employee_ids', 'in', self.ids), ('child_ids', '=', False)], ['employee_ids'], ['__count'])
        result = {employee.id: count for employee, count in read_group_result}
        for employee in self:
            employee.goals_count = result.get(employee.id, 0)

    @api.depends('ongoing_appraisal_count', 'company_id.appraisal_plan', 'company_id.duration_after_recruitment', 'company_id.duration_first_appraisal', 'company_id.duration_next_appraisal')
    def _compute_next_appraisal_date(self):
        self.filtered('ongoing_appraisal_count').next_appraisal_date = False
        employees_without_appraisal = self.filtered(lambda e: e.ongoing_appraisal_count == 0 and e.company_id.appraisal_plan)
        dates = employees_without_appraisal._upcoming_appraisal_creation_date()
        for employee in employees_without_appraisal:
            employee.next_appraisal_date = dates[employee.id]

    @api.depends('appraisal_ids.state', 'appraisal_ids.date_close')
    def _compute_last_ongoing_appraisal_date(self):
        for employee in self:
            ongoing_appraisals = employee.appraisal_ids.filtered(lambda appraisal: appraisal.state in ['1_new', '2_pending'])
            if ongoing_appraisals:
                employee.last_ongoing_appraisal_date = max(ongoing_appraisals.mapped('date_close'))
                employee.is_last_appraisal_late = employee.last_ongoing_appraisal_date < fields.Date.today()
            else:
                employee.last_ongoing_appraisal_date = False
                employee.is_last_appraisal_late = False

    def _upcoming_appraisal_creation_date(self):
        today = fields.Date.today()
        dates = {}
        for employee in self:
            if employee.appraisal_count == 0:
                months = employee.company_id.duration_after_recruitment
                starting_date = employee._get_appraisal_plan_starting_date() or today
            else:
                months = employee.company_id.duration_first_appraisal if employee.appraisal_count == 1 else employee.company_id.duration_next_appraisal
                starting_date = employee.last_appraisal_id.date_close

            if starting_date:
                # In case proposed next_appraisal_date is in the past, start counting from now
                starting_date = starting_date.date() if isinstance(starting_date, datetime.datetime) else starting_date
                original_next_appraisal_date = starting_date + relativedelta(months=months)
                dates[employee.id] = original_next_appraisal_date if original_next_appraisal_date >= today else today + relativedelta(months=months)
            else:
                dates[employee.id] = today + relativedelta(months=months)
        return dates

    def action_open_goals(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('hr_appraisal.action_hr_appraisal_goal')
        action.update({
            'domain': [('employee_ids', '=', self.id), ('child_ids', '=', False)],
            'context': {'default_employee_ids': self.ids},
        })
        return action

    def action_open_employee_appraisals(self):
        self.ensure_one()
        if self.appraisal_count == 1 and self.appraisal_ids:
            return {
                'res_model': 'hr.appraisal',
                'view_mode': 'form',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': self.appraisal_ids[0].id,
            }
        # Reuse the action in hr.appraisal to open the employee's previous appraisals
        return self.appraisal_ids[:1].action_open_employee_appraisals()

    @api.ondelete(at_uninstall=False)
    def _unlink_expect_goal_manager(self):
        is_goal_manager = self.env['hr.appraisal.goal'].search_count([('manager_ids', 'in', self.ids)])
        if is_goal_manager:
            raise UserError(self.env._("You cannot delete an employee who is a goal's manager, archive it instead."))
