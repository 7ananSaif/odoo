# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
import datetime
import logging

from odoo import api, fields, models

from odoo.exceptions import UserError
from odoo.tools import convert
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)


class HrAppraisal(models.Model):
    _name = 'hr.appraisal'
    _inherit = ['hr.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Employee Appraisal"
    _order = 'state, date_close, id desc'
    _rec_name = 'employee_id'
    _mail_post_access = 'read'

    def _get_default_employee(self):
        if self.env.context.get('active_model') in ('hr.employee', 'hr.employee.public') and 'active_id' in self.env.context:
            return self.env.context.get('active_id')
        elif self.env.context.get('active_model') == 'res.users' and 'active_id' in self.env.context:
            return self.env['res.users'].browse(self.env.context['active_id']).employee_id
        if not self.env.user.has_group('hr_appraisal.group_hr_appraisal_user'):
            return self.env.user.employee_id

    active = fields.Boolean(default=True)
    employee_id = fields.Many2one(
        'hr.employee', required=True, string='Employee', index=True,
        default=_get_default_employee, ondelete='cascade')
    employee_user_id = fields.Many2one('res.users', string="Employee User", related='employee_id.user_id')
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True)
    department_id = fields.Many2one(
        'hr.department', compute='_compute_department_id', string='Department', store=True)
    job_id = fields.Many2one('hr.job', compute='_compute_job_id', string='Job', store=True)
    image_128 = fields.Image(related='employee_id.image_128')
    image_1920 = fields.Image(related='employee_id.image_1920')
    avatar_128 = fields.Image(related='employee_id.avatar_128')
    avatar_1920 = fields.Image(related='employee_id.avatar_1920')
    last_appraisal_id = fields.Many2one('hr.appraisal', related='employee_id.last_appraisal_id')
    employee_appraisal_count = fields.Integer(related='employee_id.appraisal_count')
    uncomplete_goals_count = fields.Integer(related='employee_id.uncomplete_goals_count')
    appraisal_template_id = fields.Many2one('hr.appraisal.template', string="Appraisal Template", compute="_compute_appraisal_template",
        check_company=True, store=True, readonly=False, domain="[('department_ids', 'in', [department_id, False])]")
    employee_feedback_template = fields.Html(compute='_compute_feedback_templates', translate=True)
    manager_feedback_template = fields.Html(compute='_compute_feedback_templates', translate=True)

    date_close = fields.Date(
        string='Appraisal Date', help='Closing date of the current appraisal', required=True, index=True,
        default=lambda self: datetime.date.today() + relativedelta(months=+1))
    next_appraisal_date = fields.Date(related="employee_id.next_appraisal_date",
        help='Date where the new appraisal will be automatically created', readonly=False)
    state = fields.Selection(
        [('1_new', 'Draft'),
         ('2_pending', 'Ongoing'),
         ('3_done', 'Done')],
        string='Status', tracking=True, required=True, copy=False,
        default='1_new', index=True, group_expand=True)
    manager_ids = fields.Many2many(
        'hr.employee', 'appraisal_manager_rel', 'hr_appraisal_id',
        default=lambda self: self.env.user.employee_id,
        context={'active_test': False},
        domain="[('id', '!=', employee_id), ('active', '=', 'True'), '|', ('company_id', '=', False), ('company_id', 'in', allowed_company_ids)]")
    is_manager = fields.Boolean(compute='_compute_user_manager_rights')
    employee_autocomplete_ids = fields.Many2many('hr.employee', compute='_compute_employee_autocomplete', compute_sudo=True)
    waiting_feedback = fields.Boolean(
        string="Waiting Feedback from Employee/Managers", compute='_compute_waiting_feedback')
    employee_feedback = fields.Html(compute='_compute_employee_feedback', store=True, readonly=False, groups="hr_appraisal.group_hr_appraisal_user")
    accessible_employee_feedback = fields.Html(compute='_compute_accessible_employee_feedback', inverse="_inverse_accessible_employee_feedback")
    show_employee_feedback_full = fields.Boolean(compute='_compute_show_employee_feedback_full')
    manager_feedback = fields.Html(compute='_compute_manager_feedback', store=True, readonly=False, groups="hr_appraisal.group_hr_appraisal_user")
    accessible_manager_feedback = fields.Html(compute='_compute_accessible_manager_feedback', inverse="_inverse_accessible_manager_feedback")
    show_manager_feedback_full = fields.Boolean(compute='_compute_show_manager_feedback_full')
    employee_feedback_published = fields.Boolean(string="Employee Feedback Published", default=True, tracking=True,
        help="If greened, the manager will be able to see and edit your feedback. Otherwise, your feedback is blurred and visible only to you.")
    manager_feedback_published = fields.Boolean(string="Manager Feedback Published", default=True, tracking=True,
        help="If greened, the employee will be able to see your feedback. Otherwise, your feedback is blurred and visible only to you.")
    can_see_employee_publish = fields.Boolean(compute='_compute_buttons_display')
    can_see_manager_publish = fields.Boolean(compute='_compute_buttons_display')
    assessment_note = fields.Many2one('hr.appraisal.note', string="Final Rating", help="This field is not visible to the Employee.", check_company=True)
    note = fields.Html(string="Private Note")
    appraisal_plan_posted = fields.Boolean()
    appraisal_properties = fields.Properties("Properties", definition="department_id.appraisal_properties_definition", precompute=False)
    duplicate_appraisal_id = fields.Many2one('hr.appraisal', compute='_compute_duplicate_appraisal_id', export_string_translation=False, store=False)

    @api.depends('employee_id', 'manager_ids')
    def _compute_duplicate_appraisal_id(self):
        """
        Note: We only care for duplicate_appraisal_id when we create a
        new appraisal. This field is currently only used in form view
        and for performance reasons it should rather stay that way.
        """
        ongoing_appraisals = self.search([
            ('state', 'in', ['1_new', '2_pending']),
            ('employee_id', 'in', self.employee_id.ids),
            ('manager_ids', 'in', self.manager_ids.ids),
        ], order='date_close')
        self.duplicate_appraisal_id = False
        for appraisal in self:
            if appraisal.id or appraisal.state != '1_new':
                continue
            for ongoing_appraisal in ongoing_appraisals:
                if ongoing_appraisals.manager_ids == appraisal.manager_ids._origin\
                    and ongoing_appraisal.employee_id == appraisal.employee_id\
                        and ongoing_appraisal.id != appraisal.id:
                    appraisal.duplicate_appraisal_id = ongoing_appraisal.id
                    break

    @api.depends('employee_id.department_id', 'state')
    def _compute_department_id(self):
        for appraisal in self.filtered(lambda a: a.state == '1_new'):
            appraisal.department_id = appraisal.employee_id.department_id

    @api.depends('employee_id.job_id', 'state')
    def _compute_job_id(self):
        for appraisal in self.filtered(lambda a: a.state == '1_new'):
            appraisal.job_id = appraisal.employee_id.job_id

    @api.depends_context('uid')
    @api.depends('employee_id', 'manager_ids')
    def _compute_buttons_display(self):
        new_appraisals = self.filtered(lambda a: a.state == '1_new')
        new_appraisals.update({
            'can_see_employee_publish': False,
            'can_see_manager_publish': False,
        })
        user_employees = self.env.user.employee_ids
        is_manager = self.env.user.has_group('hr_appraisal.group_hr_appraisal_user')
        for appraisal in self:
            user_employee_in_appraisal_manager = bool(set(user_employees.ids) & set(appraisal.manager_ids.ids))
            # Appraisal manager can edit feedback in draft state
            appraisal.can_see_employee_publish = appraisal.employee_id in user_employees or \
                (user_employee_in_appraisal_manager and appraisal.state == '1_new')
            appraisal.can_see_manager_publish = user_employee_in_appraisal_manager
        for appraisal in self - new_appraisals:
            if is_manager and not appraisal.can_see_employee_publish and not appraisal.can_see_manager_publish:
                appraisal.can_see_employee_publish, appraisal.can_see_manager_publish = True, True

    @api.depends_context('uid')
    @api.depends('manager_ids', 'employee_id', 'employee_id.parent_id')
    def _compute_employee_autocomplete(self):
        self.employee_autocomplete_ids = self.env.user.get_employee_autocomplete_ids()

    @api.depends_context('uid')
    @api.depends('manager_ids', 'employee_id', 'employee_id.parent_id')
    def _compute_user_manager_rights(self):
        for appraisal in self:
            appraisal.is_manager =\
                self.env.user.has_group('hr_appraisal.group_hr_appraisal_user')\
                or self.env.user.employee_ids in (appraisal.manager_ids | appraisal.employee_id.parent_id)

    @api.depends_context('uid')
    @api.depends('employee_id', 'employee_feedback_published')
    def _compute_show_employee_feedback_full(self):
        for appraisal in self:
            is_appraisee = appraisal.employee_id.user_id == self.env.user
            appraisal.show_employee_feedback_full = is_appraisee and not appraisal.employee_feedback_published

    @api.depends_context('uid')
    @api.depends('manager_ids', 'manager_feedback_published')
    def _compute_show_manager_feedback_full(self):
        for appraisal in self:
            is_appraiser = self.env.user in appraisal.manager_ids.user_id
            appraisal.show_manager_feedback_full = is_appraiser and not appraisal.manager_feedback_published

    @api.depends('department_id', 'appraisal_template_id')
    def _compute_employee_feedback(self):
        for appraisal in self.filtered(lambda a: a.state in ['1_new', '2_pending']):
            employee_template = appraisal._get_appraisal_template('employee')
            if appraisal.state == '1_new':
                appraisal.employee_feedback = employee_template
            else:
                appraisal.employee_feedback = appraisal.employee_feedback or employee_template

    @api.depends('department_id', 'appraisal_template_id')
    def _compute_manager_feedback(self):
        for appraisal in self.filtered(lambda a: a.state in ['1_new', '2_pending']):
            manager_template = appraisal._get_appraisal_template('manager')
            if appraisal.state == '1_new':
                appraisal.manager_feedback = manager_template
            else:
                appraisal.manager_feedback = appraisal.manager_feedback or manager_template

    @api.depends('department_id', 'company_id', 'appraisal_template_id')
    def _compute_feedback_templates(self):
        for appraisal in self:
            appraisal.employee_feedback_template = appraisal._get_appraisal_template('employee')
            appraisal.manager_feedback_template = appraisal._get_appraisal_template('manager')

    @api.depends('department_id')
    def _compute_appraisal_template(self):
        all_department_template_ids = self.env['hr.appraisal.template'].search(
            [('department_ids', '=', False), ('company_id', 'in', self.department_id.company_id.ids + [False])])
        for appraisal in self:
            appraisal.appraisal_template_id = appraisal.appraisal_template_id or \
                appraisal.department_id.appraisal_template_ids[:1] or \
                all_department_template_ids.filtered(lambda t: t.company_id.id in [appraisal.department_id.company_id.id, False])[:1]

    @api.depends('employee_feedback_published', 'manager_feedback_published')
    def _compute_waiting_feedback(self):
        for appraisal in self:
            appraisal.waiting_feedback = not appraisal.employee_feedback_published or not appraisal.manager_feedback_published

    @api.depends('employee_id', 'date_close')
    @api.depends_context('include_date_in_name')
    def _compute_display_name(self):
        if not self.env.context.get('include_date_in_name'):
            return super()._compute_display_name()
        for appraisal in self:
            appraisal.display_name = self.env._(
                "Appraisal for %(employee)s on %(date)s",
                employee=appraisal.employee_id.name, date=appraisal.date_close)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        self = self.sudo()  # fields are not on the employee public
        if self.employee_id:
            manager = self.employee_id.parent_id or self.env.user.employee_id
            self.manager_ids = manager if manager != self.employee_id else False
            # Allow indirect managers to request appraisals for employees
            if self.env.user.employee_id != self.employee_id and not self.env.user.has_group('hr_appraisal.group_hr_appraisal_user'):
                self.manager_ids |= self.env.user.employee_id
            self.department_id = self.employee_id.department_id

    def subscribe_employees(self):
        for appraisal in self:
            partners_ids = (appraisal.manager_ids.sudo().related_partner_id + appraisal.employee_id.sudo().related_partner_id).ids
            appraisal.message_subscribe(partner_ids=partners_ids)

    def send_appraisal(self):
        # TDE FIXME: probably some cleanup to do here
        for appraisal in self:
            confirmation_mail_template = appraisal.company_id.appraisal_confirm_mail_template
            mapped_data = {
                **{appraisal.employee_id: confirmation_mail_template},
                **{manager: confirmation_mail_template for manager in appraisal.manager_ids}
            }
            for employee, mail_template in mapped_data.items():
                if not employee.work_email or not self.env.user.email or not mail_template:
                    continue
                ctx = {
                    'employee_to_name': appraisal.employee_id.name,
                    'recipient_users': employee.user_id,
                    'url': '/mail/view?model=%s&res_id=%s' % ('hr.appraisal', appraisal.id),
                }
                mail_template = mail_template.with_context(**ctx)
                subject = mail_template._render_field('subject', appraisal.ids)[appraisal.id]
                body = mail_template._render_field('body_html', appraisal.ids)[appraisal.id]
                # post the message
                mail_values = {
                    'email_from': self.env.user.email_formatted,
                    'author_id': self.env.user.partner_id.id,
                    'model': None,
                    'res_id': None,
                    'subject': subject,
                    'body_html': body,
                    'auto_delete': True,
                    'email_to': employee.work_email
                }
                mail_values['body_html'] = self.env['mail.render.mixin']._render_encapsulate(
                    'mail.mail_notification_light', mail_values['body_html'],
                    context_record=appraisal,
                    add_context={
                        'record_name': self.env._("Appraisal Request"),
                    },
                )
                self.env['mail.mail'].sudo().create(mail_values)

                from_cron = 'from_cron' in self.env.context
                # When cron creates appraisal, it creates specific activities
                # In this case, no need to create activities, not to be repetitive
                if employee.user_id and not from_cron:
                    appraisal.activity_schedule(
                        'mail.mail_activity_data_todo', appraisal.date_close,
                        summary=self.env._('Appraisal Form to Fill'),
                        note=self.env._('Fill appraisal for %s', appraisal.employee_id._get_html_link()),
                        user_id=employee.user_id.id)

    @api.model_create_multi
    def create(self, vals_list):
        appraisals = super().create(vals_list)
        appraisals_to_send = self.env['hr.appraisal']
        for appraisal, vals in zip(appraisals, vals_list):
            if vals.get('state') and vals['state'] == '2_pending':
                appraisals_to_send |= appraisal
            if vals.get('state') and vals['state'] == '1_new':
                appraisal.employee_id.sudo().write({
                    'last_appraisal_id': appraisal.id,
                })
        appraisals_to_send.send_appraisal()
        # TDE FIXME: check if we can use suggested recipients instead (master)
        appraisals.subscribe_employees()
        return appraisals

    @api.depends('employee_feedback', 'can_see_employee_publish', 'employee_feedback_published')
    def _compute_accessible_employee_feedback(self):
        for appraisal in self:
            if appraisal.can_see_employee_publish or appraisal.employee_feedback_published:
                appraisal.accessible_employee_feedback = appraisal.sudo().employee_feedback
            else:
                appraisal.accessible_employee_feedback = self.env._("Unpublished")

    def _inverse_accessible_employee_feedback(self):
        for appraisal in self:
            if appraisal.can_see_employee_publish:
                appraisal.sudo().employee_feedback = appraisal.accessible_employee_feedback
            else:
                raise UserError(self.env._('The employee feedback cannot be changed by managers.'))

    @api.depends('manager_feedback', 'can_see_manager_publish', 'manager_feedback_published')
    def _compute_accessible_manager_feedback(self):
        for appraisal in self:
            if appraisal.can_see_manager_publish or appraisal.manager_feedback_published:
                appraisal.accessible_manager_feedback = appraisal.sudo().manager_feedback
            else:
                appraisal.accessible_manager_feedback = self.env._("Unpublished")

    def _inverse_accessible_manager_feedback(self):
        for appraisal in self:
            if appraisal.can_see_manager_publish:
                appraisal.sudo().manager_feedback = appraisal.accessible_manager_feedback
            else:
                raise UserError(self.env._('The manager feedback cannot be changed by an employee.'))

    def _get_appraisal_template(self, template):
        self.ensure_one()
        if not self.appraisal_template_id:
            return False
        if template == 'employee':
            return self.appraisal_template_id.appraisal_employee_feedback_template
        else:
            return self.appraisal_template_id.appraisal_manager_feedback_template

    def _find_previous_appraisals(self):
        result = {}
        all_appraisals = self.env['hr.appraisal'].search([
            ('employee_id', 'in', self.mapped('employee_id').ids),
        ], order='employee_id, id desc')
        for appraisal in self:
            previous_appraisals = all_appraisals.filtered(lambda x: x.employee_id == appraisal.employee_id and x.id != appraisal.id and x.create_date < appraisal.create_date)
            if previous_appraisals:
                result[appraisal.id] = previous_appraisals[0]
        return result

    def write(self, vals):
        if 'manager_feedback_published' in vals and not all(a.can_see_manager_publish for a in self):
            raise UserError(self.env._('The "Manager Feedback Published" cannot be changed by an employee.'))

        force_published = self.env['hr.appraisal']
        if vals.get('employee_feedback_published'):
            user_employees = self.env.user.employee_ids
            force_published = self.filtered(lambda a: (a.is_manager) and not (a.employee_feedback_published or a.employee_id in user_employees))
        if vals.get('state') in ['2_pending', '3_done']:
            self.activity_ids.action_feedback()
            not_done_appraisal = self.env['hr.appraisal']
            for appraisal in self:
                appraisal.employee_id.sudo().write({
                    'last_appraisal_id': appraisal.id,
                })
                if appraisal.state != '3_done':
                    not_done_appraisal |= appraisal
            if vals.get('state') == '2_pending':
                vals['employee_feedback_published'] = False
                vals['manager_feedback_published'] = False
                not_done_appraisal.send_appraisal()
            else:
                vals['employee_feedback_published'] = True
                vals['manager_feedback_published'] = True
                self._appraisal_plan_post()
                if self.env.user.partner_id.email_formatted:
                    body = self.env._("The appraisal's status has been set to Done by %s", self.env.user.name)
                    self.message_notify(
                        body=body,
                        subject=self.env._("Your Appraisal has been completed"),
                        partner_ids=appraisal.message_partner_ids.ids,
                    )
                    self.message_post(body=body)
        result = super().write(vals)
        if force_published:
            for appraisal in force_published:
                role = self.env._('Manager') if self.env.user.employee_id in appraisal.manager_ids else self.env._('Appraisal Officer')
                appraisal.message_post(body=self.env._('%(user)s decided, as %(role)s, to publish the employee\'s feedback', user=self.env.user.name, role=role))
        return result

    def unlink(self):
        previous_appraisals = self._find_previous_appraisals()
        for appraisal in self:
            # If current appraisal is the last_appraisal_id for the employee we should update last_appraisal_id bfore deleting
            if appraisal.employee_id and appraisal.employee_id.last_appraisal_id == appraisal:
                previous_appraisal = previous_appraisals.get(appraisal.id)
                appraisal.employee_id.sudo().write({
                    'last_appraisal_id': previous_appraisal.id if previous_appraisal else False,
                })
        return super(HrAppraisal, self).unlink()

    def _appraisal_plan_post(self):
        odoobot = self.env.ref('base.partner_root')
        dates = self.employee_id.sudo()._upcoming_appraisal_creation_date()
        for appraisal in self:
            # The only ongoing appraisal is the current one
            if not appraisal.appraisal_plan_posted and appraisal.company_id.appraisal_plan and appraisal.employee_id.sudo().ongoing_appraisal_count == 1:
                date = dates[appraisal.employee_id.id]
                formated_date = format_date(self.env, date, date_format="MMM d y")
                body = self.env._('Thanks to your Appraisal Plan, without any new manual Appraisal, the new Appraisal will be automatically created on %s.', formated_date)
                appraisal._message_log(body=body, author_id=odoobot.id)
                appraisal.appraisal_plan_posted = True

    def _generate_activities(self):
        today = fields.Date.today()
        for appraisal in self:
            employee = appraisal.employee_id
            managers = appraisal.manager_ids
            last_appraisal_date = employee.last_appraisal_id.date_close
            last_appraisal_months = last_appraisal_date and (
                today.year - last_appraisal_date.year) * 12 + (today.month - last_appraisal_date.month)
            if employee.user_id:
                # an appraisal has been just created
                if employee.appraisal_count == 1:
                    months = (appraisal.date_close.year - employee.create_date.year) * \
                        12 + (appraisal.date_close.month - employee.create_date.month)
                    note = self.env._("You arrived %s months ago. Your appraisal is created and you can fill it here.", months)
                else:
                    note = self.env._("Your last appraisal was %s months ago. Your appraisal is created and you can fill it here.", last_appraisal_months)
                appraisal.with_context(mail_activity_quick_update=True).activity_schedule(
                    'mail.mail_activity_data_todo', today,
                    summary=self.env._('Appraisal to fill'),
                    note=note, user_id=employee.user_id.id)
                for manager in managers.filtered('user_id'):
                    if employee.appraisal_count == 1:
                        note = self.env._(
                            "The employee %(employee)s arrived %(months)s months ago. The appraisal is created and you can fill it here.",
                            employee=employee._get_html_link(), months=months)
                    else:
                        note = self.env._(
                            "The last appraisal of %(employee)s was %(months)s months ago. The appraisal is created and you can fill it here.",
                            employee=appraisal.employee_id._get_html_link(), months=last_appraisal_months)
                    appraisal.with_context(mail_activity_quick_update=True).activity_schedule(
                        'mail.mail_activity_data_todo', today,
                        summary=self.env._('Appraisal for %s to fill', employee.name),
                        note=note, user_id=manager.user_id.id)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_new_or_cancel(self):
        if any(appraisal.state != '1_new' for appraisal in self):
            raise UserError(self.env._("Oops! You can only delete draft appraisals."))

    def read(self, fields=None, load='_classic_read'):
        fields_set = set(fields) if fields is not None else set()
        check_feedback = fields_set & {'manager_feedback', 'employee_feedback'}
        check_notes = fields_set & {'note', 'assessment_note'}
        if check_feedback:
            fields = fields + ['can_see_employee_publish', 'can_see_manager_publish', 'employee_feedback_published', 'manager_feedback_published']
        if check_notes:
            fields = fields + ['employee_id']
        records = super().read(fields, load)
        if check_notes:
            for appraisal in records:
                if appraisal['employee_id'] == self.env.user.employee_id.id:
                    appraisal['note'] = self.env._('Note')
                    appraisal['assessment_note'] = False
        return records

    def action_calendar_event(self):
        self.ensure_one()
        partners = self.manager_ids.mapped('related_partner_id') | self.employee_id.related_partner_id | self.env.user.partner_id
        action = self.env["ir.actions.actions"]._for_xml_id("calendar.action_calendar_event")
        action['context'] = {
            'default_partner_ids': partners.ids,
            'default_res_model': 'hr.appraisal',
            'default_res_id': self.id,
            'default_name': self.env._('Appraisal of %s', self.employee_id.name),
            'initial_date': self.date_close,
        }
        action['domain'] = [('partner_ids', 'in', partners.ids)]
        return action

    def action_confirm(self):
        self.state = '2_pending'

    def action_done(self):
        appraisals_with_rating = self.filtered('assessment_note')
        appraisals_with_rating.state = '3_done'
        if self - appraisals_with_rating:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Required:',
                    'message': self.env._('Please set a final rating to validate these appraisals:\n- %s',
                                    '\n- '.join((self - appraisals_with_rating).mapped('display_name'))),
                    'type': 'danger',
                    'sticky': True
                }
            }

    def action_back(self):
        self.state = '1_new'
        self.assessment_note = False

    def action_reopen(self):
        self.state = '2_pending'

    def action_open_employee_appraisals(self):
        view_id = self.env.ref('hr_appraisal.hr_appraisal_view_tree_orderby_create_date').id
        return {
            'name': self.env._('Previous Appraisals'),
            'res_model': 'hr.appraisal',
            'view_mode': 'list,kanban,form,gantt,calendar,activity',
            'views': [(view_id, 'list'), (False, 'kanban'), (False, 'form'), (False, 'gantt'), (False, 'calendar'), (False, 'activity')],
            'domain': [('employee_id', '=', self.employee_id.ids)],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'search_default_groupby_date_close': True,
            }
        }

    def action_open_goals(self):
        self.ensure_one()
        return {
            'name': self.env._("%s's Goals", self.employee_id.name),
            'view_mode': 'kanban,list,form,graph',
            'res_model': 'hr.appraisal.goal',
            'type': 'ir.actions.act_window',
            'views': [
                (self.env.ref('hr_appraisal.hr_appraisal_goal_view_tree').id, 'list'),
                (False, 'kanban'),
                (self.env.ref('hr_appraisal.hr_appraisal_goal_view_form').id, 'form'),
                (False, 'graph'),
            ],
            'target': 'current',
            'domain': [('employee_ids', '=', self.employee_id.id), ('child_ids', '=', False)],
            'context': {'default_employee_ids': self.employee_id.ids},
        }

    def action_send_appraisal_request(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'request.appraisal',
            'target': 'new',
            'name': self.env._('Appraisal Request'),
            'context': {'default_appraisal_id': self.id},
        }

    def action_open_appraisal_campaign_wizard(self):
        employee_ids = False
        if self.env.context.get('active_model') == 'hr.employee':
            employee_ids = self.env.context.get('active_ids')
        elif self.env.context.get('active_model') == 'hr.appraisal':
            appraisals = self.env['hr.appraisal'].browse(self.env.context.get('active_ids'))
            employee_ids = appraisals.employee_id.ids
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Appraisal Campaign'),
            'res_model': 'hr.appraisal.campaign.wizard',
            'view_mode': 'form',
            'context': {
                'default_mode': 'employee',
                'default_employee_ids': employee_ids,
            },
            'target': 'new',
        }

    @api.model
    def has_demo_data(self):
        if not self.env.user.has_group("hr_appraisal.group_hr_appraisal_user"):
            return True
        # This record only exists if the scenario has been already launched
        goal_tag = self.env.ref('hr_appraisal.hr_appraisal_goal_tag_softskills', raise_if_not_found=False)
        if goal_tag:
            return True
        return bool(self.env['ir.module.module'].search_count([
            '&',
                ('state', 'in', ['installed', 'to upgrade', 'uninstallable']),
                ('demo', '=', True)
        ]))

    def _load_demo_data(self):
        if self.has_demo_data():
            return
        env_sudo = self.sudo().with_context({}).env
        env_sudo['hr.employee']._load_scenario()
        convert.convert_file(env_sudo, 'hr_appraisal', 'data/scenarios/hr_appraisal_scenario.xml', None, mode='init')
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
