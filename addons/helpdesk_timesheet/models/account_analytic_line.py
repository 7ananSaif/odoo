# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.exceptions import ValidationError
from odoo.tools.sql import column_exists, create_column


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    helpdesk_ticket_id = fields.Many2one(
        'helpdesk.ticket', 'Ticket', index='btree_not_null',
        compute='_compute_helpdesk_ticket_id', store=True, readonly=False,
        domain="[('company_id', '=', company_id), ('project_id', '=?', project_id)]")
    project_id = fields.Many2one(inverse="_inverse_project_id")
    has_helpdesk_team = fields.Boolean(related='project_id.has_helpdesk_team', export_string_translation=False)
    display_task = fields.Boolean(compute="_compute_display_task", export_string_translation=False)

    def _auto_init(self):
        # At install implementation of `_compute_helpdesk_ticket_id` -> default value of NULL for all rows
        if not column_exists(self.env.cr, 'account_analytic_line', 'helpdesk_ticket_id'):
            create_column(self.env.cr, 'account_analytic_line', 'helpdesk_ticket_id', 'int4')
        return super()._auto_init()

    @api.depends('has_helpdesk_team', 'project_id', 'task_id', 'helpdesk_ticket_id')
    def _compute_display_task(self):
        for line in self:
            line.display_task = line.task_id or not line.has_helpdesk_team

    @api.depends('helpdesk_ticket_id')
    def _compute_project_id(self):
        timesheets_with_ticket = self.filtered('helpdesk_ticket_id')
        for timesheet in timesheets_with_ticket:
            if timesheet.validated or not timesheet.helpdesk_ticket_id.project_id or timesheet.helpdesk_ticket_id.project_id == timesheet.project_id:
                continue
            timesheet.project_id = timesheet.helpdesk_ticket_id.project_id
        super(AccountAnalyticLine, self - timesheets_with_ticket)._compute_project_id()

    def _inverse_project_id(self):
        self.filtered(
            lambda line:
                (
                    line.helpdesk_ticket_id and
                    not line.validated and
                    not line.project_id
                ) or (
                    line.project_id != line.helpdesk_ticket_id.project_id
                )
        ).helpdesk_ticket_id = False

    @api.depends('helpdesk_ticket_id')
    def _compute_task_id(self):
        # Override to set task_id to false when a helpdesk_ticket_id has been assigned
        task_and_ticket_lines = self.filtered(lambda line: line.task_id and line.helpdesk_ticket_id)
        task_and_ticket_lines.task_id = False
        self.env.remove_to_compute(self._fields['helpdesk_ticket_id'], task_and_ticket_lines)
        super(AccountAnalyticLine, self - task_and_ticket_lines)._compute_task_id()

    @api.depends('task_id', 'project_id')
    def _compute_helpdesk_ticket_id(self):
        # set helpdesk_ticket_id to false when a task_id has been assigned
        timesheet_to_update = self.filtered(lambda line: line.task_id and line.helpdesk_ticket_id or line.project_id != line.helpdesk_ticket_id.project_id)
        self.env.remove_to_compute(self._fields['task_id'], timesheet_to_update)
        timesheet_to_update.helpdesk_ticket_id = False

    @api.constrains('task_id', 'helpdesk_ticket_id')
    def _check_no_link_task_and_ticket(self):
        # Check if any timesheets are not linked to a ticket and a task at the same time
        has_linked_to_both = self.env['account.analytic.line'].search(
            [('id', 'in', self.ids),
             ('task_id', '!=', False),
             ('helpdesk_ticket_id', '!=', False)],
            limit=1,
        )
        if has_linked_to_both:
            raise ValidationError(_("You cannot link a timesheet entry to a task and a ticket at the same time."))

    @api.depends('helpdesk_ticket_id.partner_id')
    def _compute_partner_id(self):
        super()._compute_partner_id()
        for line in self:
            if line.helpdesk_ticket_id:
                line.partner_id = line.helpdesk_ticket_id.partner_id or line.partner_id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        super()._onchange_project_id()
        if not self.project_id or self.helpdesk_ticket_id.project_id != self.project_id:
            self.helpdesk_ticket_id = False

    def write(self, vals):
        if vals.get("helpdesk_ticket_id"):
            ticket = self.env['helpdesk.ticket'].sudo().browse(vals["helpdesk_ticket_id"])
            if ticket.analytic_account_id:
                vals['account_id'] = ticket.analytic_account_id.id
            if ticket.project_id:
                vals['project_id'] = ticket.project_id.id
            if 'company_id' not in vals:
                vals['company_id'] = ticket.project_id.company_id.id
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list_per_ticket_id = defaultdict(list)
        for vals in vals_list:
            if vals.get('helpdesk_ticket_id'):
                vals_list_per_ticket_id[vals['helpdesk_ticket_id']].append(vals)
        if vals_list_per_ticket_id:
            tickets_per_id = {
                ticket['id']: ticket
                for ticket in self.env['helpdesk.ticket'].sudo().browse(list(vals_list_per_ticket_id))
            }
            for ticket_id, ticket_vals_list in vals_list_per_ticket_id.items():
                ticket = tickets_per_id[ticket_id]
                vals_update = {'account_id': ticket.analytic_account_id.id}
                if ticket.project_id:
                    vals_update['project_id'] = ticket.project_id.id
                    if not vals_update.get('account_id'):
                        vals_update['account_id'] = ticket.project_id.account_id.id
                for vals in ticket_vals_list:
                    if 'company_id' not in vals:
                        vals_update['company_id'] = ticket.project_id.company_id.id or ticket.company_id.id
                    vals.update(vals_update)
        return super().create(vals_list)

    def _update_existing_timers(self, vals):
        # if the ticket changed to set a ticket or remove ticket and no task is set instead
        if 'helpdesk_ticket_id' in vals and (self.helpdesk_ticket_id or not self.task_id):
            # Check if there are some running timers linked to the timesheets to also update them.
            timers = self.env['timer.timer'].search([('res_model', '=', self._name), ('res_id', 'in', self.ids)])
            if timers:
                helpdesk_ticket_id = vals['helpdesk_ticket_id']
                timers.write({
                    'parent_res_model': 'helpdesk.ticket' if helpdesk_ticket_id else None,
                    'parent_res_id': helpdesk_ticket_id
                })
            return
        super()._update_existing_timers(vals)

    def _get_timesheet_field_and_model_name(self):
        if self.env.context.get('default_helpdesk_ticket_id', False):
            return 'helpdesk_ticket_id', 'helpdesk.ticket'
        return super()._get_timesheet_field_and_model_name()

    def _timesheet_get_portal_domain(self):
        domain = super()._timesheet_get_portal_domain()
        if not self.env.user.has_group('hr_timesheet.group_hr_timesheet_user'):
            domain = Domain.OR([domain, self._timesheet_in_helpdesk_get_portal_domain()])
        return domain

    def _timesheet_in_helpdesk_get_portal_domain(self):
        return [
            '&',
                '&',
                    '&',
                        ('task_id', '=', False),
                        ('helpdesk_ticket_id', '!=', False),
                    '|',
                        ('project_id.message_partner_ids', 'child_of', [self.env.user.partner_id.commercial_partner_id.id]),
                        ('helpdesk_ticket_id.message_partner_ids', 'child_of', [self.env.user.partner_id.commercial_partner_id.id]),
                ('project_id.privacy_visibility', '=', 'portal')
        ]

    @api.model
    def _add_time_to_timesheet_fields(self):
        return super()._add_time_to_timesheet_fields() + ['helpdesk_ticket_id']

    def _get_new_timesheet_timer_vals(self):
        return {
            **super()._get_new_timesheet_timer_vals(),
            'helpdesk_ticket_id': self.helpdesk_ticket_id.id,
        }

    def _get_last_timesheet_domain(self):
        return Domain.AND([
            super()._get_last_timesheet_domain(),
            [('helpdesk_ticket_id', '=', self.helpdesk_ticket_id.id)],
        ])

    def _get_timesheet_timer_data(self):
        timesheet_timer_data = super()._get_timesheet_timer_data()
        if 'other_company' not in timesheet_timer_data:
            timesheet_timer_data['helpdesk_ticket_id'] = self.helpdesk_ticket_id.id
            timesheet_timer_data['has_helpdesk_team'] = self.has_helpdesk_team
        return timesheet_timer_data

    def _get_timer_vals(self):
        vals = super()._get_timer_vals()
        if self.helpdesk_ticket_id:
            vals['parent_res_model'] = 'helpdesk.ticket'
            vals['parent_res_id'] = self.helpdesk_ticket_id.id
        return vals
