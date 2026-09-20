# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import random
import math
import pytz

from collections import defaultdict, Counter
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta
from functools import reduce

from odoo import api, Command, fields, models, _
from odoo.fields import Domain
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, date_utils, convert_file, format_amount
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import format_date
from odoo.tools.safe_eval import safe_eval, datetime as safe_eval_datetime, dateutil as safe_eval_dateutil

_logger = logging.getLogger(__name__)


class DefaultDictPayroll(defaultdict):
    def get(self, key, default=None):
        if key not in self and default is not None:
            self[key] = default
        return self[key]


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _description = 'Pay Slip'
    _inherit = ['mail.thread.cc', 'mail.thread.main.attachment', 'mail.activity.mixin']
    _order = 'date_to desc'

    struct_id = fields.Many2one(
        'hr.payroll.structure', string='Structure', precompute=True,
        compute='_compute_struct_id', store=True, readonly=False, tracking=True,
        help='Defines the rules that have to be applied to this payslip, according '
             'to the contract chosen. If the contract is empty, this field isn\'t '
             'mandatory anymore and all the valid rules of the structures '
             'of the employee\'s contracts will be applied.')
    structure_code = fields.Char(related="struct_id.code")
    struct_type_id = fields.Many2one('hr.payroll.structure.type', related='struct_id.type_id')
    wage_type = fields.Selection(related='version_id.wage_type')
    name = fields.Char(
        string='Payslip Name', required=True,
        compute='_compute_name', store=True, readonly=False)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id), '|', ('active', '=', True), ('active', '=', False)]")
    employee_reference = fields.Char(related='employee_id.registration_number')
    image_128 = fields.Image(related='employee_id.image_128')
    image_1920 = fields.Image(related='employee_id.image_1920')
    avatar_128 = fields.Image(related='employee_id.avatar_128')
    avatar_1920 = fields.Image(related='employee_id.avatar_1920')
    department_id = fields.Many2one('hr.department', string='Department', related='employee_id.department_id', readonly=True, store=True)
    job_id = fields.Many2one('hr.job', string='Job Position', related='employee_id.job_id', readonly=True, store=True)
    date_from = fields.Date(
        string='From', readonly=False, required=True, tracking=True,
        default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(
        string='To', readonly=False, required=True, tracking=True,
        compute="_compute_date_to", store=True, precompute=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('paid', 'Paid'),
        ('cancel', 'Canceled')],
        string='State', index=True, readonly=True, copy=False,
        default='draft', tracking=True,
        help="""* When the payslip is created the status is \'Draft\'
                \n* If the payslip is confirmed then status is set to \'Done\'.
                \n* When the user cancels a payslip, the status is \'Canceled\'.""")
    state_display = fields.Selection([
            ('draft', 'Draft'),
            ('validated', 'Done'),
            ('paid', 'Paid'),
            ('cancel', 'Canceled'),
            ('warning', 'Warning'),
            ('error', 'Error'),
        ],
        string='Status',
        compute='_compute_state_display',
        store=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        'hr.payslip.line', 'slip_id', string='Payslip Lines',
        compute='_compute_line_ids', store=True, readonly=False, copy=True)
    company_id = fields.Many2one(
        'res.company', string='Company', copy=False, required=True,
        compute='_compute_company_id', store=True, readonly=True,
        default=lambda self: self.env.company)
    country_id = fields.Many2one(
        'res.country', string='Country',
        related='company_id.country_id', readonly=True
    )
    country_code = fields.Char(related='country_id.code', depends=['country_id'], readonly=True)
    worked_days_line_ids = fields.One2many(
        'hr.payslip.worked_days', 'payslip_id', string='Payslip Worked Days', copy=True,
        compute='_compute_worked_days_line_ids', store=True, readonly=False)
    input_line_ids = fields.One2many(
        'hr.payslip.input', 'payslip_id', string='Payslip Inputs',
        compute='_compute_input_line_ids', store=True,
        readonly=False)
    paid = fields.Boolean(
        string='Made Payment Order? ', copy=False)
    done_date = fields.Datetime(string="payslip confirmation Date")
    paid_date = fields.Date(string="Payment Date")
    note = fields.Text(string='Internal Note')
    version_id = fields.Many2one(
        'hr.version',
        string='Employee Record',
        precompute=True,
        tracking=True,
        compute='_compute_version_id',
        store=True,
        readonly=False,
        index=True,
        domain="""[
            ('contract_date_start', '<=', date_end),
            '|', ('contract_date_end', '=', False), ('contract_date_end', '>=', date_from)
        ]""",
    )
    credit_note = fields.Boolean(
        string='Credit Note',
        help="Indicates this payslip has a refund of another")
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Pay Run',
        copy=False, ondelete='cascade', tracking=True, index='btree_not_null',
        domain="[('company_id', '=', company_id)]")
    sum_worked_hours = fields.Float(compute='_compute_worked_hours', store=True, help='Total hours of attendance and time off (paid or not)')
    compute_date = fields.Date('Computed On')
    basic_wage = fields.Monetary(compute='_compute_basic_net', store=True)
    gross_wage = fields.Monetary(compute='_compute_basic_net', store=True)
    net_wage = fields.Monetary(compute='_compute_basic_net', store=True)
    currency_id = fields.Many2one(related='version_id.currency_id')
    is_regular = fields.Boolean(compute='_compute_is_regular')
    is_wrong_version = fields.Boolean(compute='_compute_is_wrong_version', store=True)
    has_wrong_data = fields.Boolean(compute='_compute_is_wrong_version', store=True)
    keep_wrong_version = fields.Boolean(default=False)
    has_negative_net_to_report = fields.Boolean()
    is_superuser = fields.Boolean(compute="_compute_is_superuser")
    edited = fields.Boolean()
    queued_for_pdf = fields.Boolean(default=False)

    issues = fields.Json(compute='_compute_issues', store=True, readonly=True)
    warning_count = fields.Integer(compute='_compute_issues', store=True, readonly=True)
    error_count = fields.Integer(compute='_compute_issues', store=True, readonly=True)
    is_wrong_duration = fields.Boolean(compute='_compute_is_wrong_duration', compute_sudo=True)
    negative_net_to_report_message = fields.Char(compute='_compute_negative_net_to_report_display')
    negative_net_to_report_amount = fields.Float(compute='_compute_negative_net_to_report_display')
    negative_net_to_report_display = fields.Boolean(compute='_compute_negative_net_to_report_display')

    salary_attachment_ids = fields.Many2many(
        'hr.salary.attachment',
        relation='hr_payslip_hr_salary_attachment_rel',
        string='Salary Adjustments',
        compute='_compute_salary_attachment_ids',
        store=True,
        readonly=False,
    )
    salary_attachment_count = fields.Integer('Salary Adjustment count', compute='_compute_salary_attachment_count')
    use_worked_day_lines = fields.Boolean(related="struct_id.use_worked_day_lines")
    payment_report = fields.Binary(
        string='Payment Report',
        help="Export .csv file related to this payslip",
        readonly=True)
    payment_report_filename = fields.Char(readonly=True)
    payment_report_date = fields.Date(readonly=True)
    ytd_computation = fields.Boolean(related='struct_id.ytd_computation')
    employer_cost = fields.Monetary(compute='_compute_basic_net', store=True, string='Employer Cost')
    is_refund_payslip = fields.Boolean(string="Is Refund payslip", default=False)
    is_refunded = fields.Boolean(string="Is Refunded", default=False)
    is_corrected = fields.Boolean(string="Is Corrected", default=False)
    origin_payslip_id = fields.Many2one('hr.payslip', string='Origin Payslip', index='btree_not_null')
    related_payslip_ids = fields.One2many('hr.payslip', 'origin_payslip_id', string="Related Payslips")
    related_payslip_count = fields.Integer("Related payslip count", compute="_compute_related_payslip_count_count")
    payslip_properties = fields.Properties('Payroll Properties', definition='struct_id.payslip_properties_definition')

    def _get_salary_advance_balances(self):
        return defaultdict(float)

    @api.model
    def _schedule_period_start(self, schedule, today, country_code=False):
        week_start = self.env["res.lang"]._get_data(code=self.env.user.lang).week_start
        if schedule == 'quarterly':
            current_year_quarter = math.ceil(today.month / 3)
            date_from = today.replace(day=1, month=(current_year_quarter - 1) * 3 + 1)
        elif schedule == 'semi-annually':
            is_second_half = math.floor((today.month - 1) / 6)
            date_from = today.replace(day=1, month=7) if is_second_half else today.replace(day=1, month=1)
        elif schedule == 'annually':
            date_from = today.replace(day=1, month=1)
        elif schedule == 'weekly':
            week_day = today.weekday()
            date_from = today + relativedelta(days=-week_day)
        elif schedule == 'bi-weekly':
            week = int(today.strftime("%U") if week_start == '7' else today.strftime("%W"))
            week_day = today.weekday()
            is_second_week = week % 2 == 0
            date_from = today + relativedelta(days=-week_day - 7 * int(is_second_week))
        elif schedule == 'semi-monthly':
            date_from = today.replace(day=1 if today.day < 15 else 15)
        elif schedule == 'bi-monthly':
            current_year_slice = math.ceil(today.month / 2)
            date_from = today.replace(day=1, month=(current_year_slice - 1) * 2 + 1)
        elif schedule == 'daily':
            date_from = today
        else:  # if not handled, put the monthly behaviour
            date_from = today.replace(day=1)
        return date_from

    @api.model_create_multi
    def create(self, vals_list):
        payslips = super().create(vals_list)
        payslips._compute_payslip_properties()
        return payslips

    def _compute_payslip_properties(self):
        properties_definition_per_structure = defaultdict(list)
        for struct in self.mapped('struct_id'):
            properties_definition_per_structure[struct] = struct._get_common_payroll_properties()

        for payslip in self:
            payslip_properties = dict(payslip.payslip_properties) or {}
            if payslip.state in ['paid', 'done']:
                continue
            version_properties = dict(payslip.version_id.payroll_properties)
            payslip_properties.update({
                key: version_properties.get(key, 0) for key in properties_definition_per_structure[payslip.struct_id]
            })
            payslip.update({
                'payslip_properties': payslip_properties
            })

    @api.depends('error_count', 'warning_count', 'state')
    def _compute_state_display(self):
        for payslip in self:
            if payslip.error_count:
                payslip.state_display = 'error'
            elif payslip.warning_count:
                payslip.state_display = 'warning'
            else:
                payslip.state_display = payslip.state

    @api.model
    def _schedule_timedelta(self, schedule, date_from, country_code=False):
        if schedule == 'quarterly':
            timedelta = relativedelta(months=3, days=-1)
        elif schedule == 'semi-annually':
            timedelta = relativedelta(months=6, days=-1)
        elif schedule == 'annually':
            timedelta = relativedelta(years=1, days=-1)
        elif schedule == 'weekly':
            timedelta = relativedelta(days=6)
        elif schedule == 'bi-weekly':
            timedelta = relativedelta(days=13)
        elif schedule == 'semi-monthly':
            timedelta = relativedelta(day=15 if date_from.day < 15 else 31)
        elif schedule == 'bi-monthly':
            timedelta = relativedelta(months=2, days=-1)
        elif schedule == 'daily':
            timedelta = relativedelta(days=0)
        else:  # if not handled, put the monthly behaviour
            timedelta = relativedelta(months=1, days=-1)
        return timedelta

    def _get_schedule_timedelta(self):
        self.ensure_one()
        schedule = self.version_id.schedule_pay or self.version_id.structure_type_id.default_schedule_pay
        return self._schedule_timedelta(schedule, self.date_from)

    @api.depends('date_from', 'version_id', 'struct_id')
    def _compute_date_to(self):
        for payslip in self:
            if self.env.context.get('default_date_to'):
                payslip.date_to = self.env.context.get('default_date_to')
            else:
                payslip.date_to = payslip.date_from and payslip.date_from + payslip._get_schedule_timedelta()

    @api.depends('employee_id', 'version_id', 'struct_id', 'date_from', 'date_to', 'struct_id')
    def _compute_input_line_ids(self):
        attachment_type_ids = self.env['hr.payslip.input.type'].search([('available_in_attachments', '=', True)]).ids
        for slip in self:
            if not slip.employee_id or not slip.employee_id.salary_attachment_ids or not slip.struct_id:
                lines_to_remove = slip.input_line_ids.filtered(lambda x: x.input_type_id.id in attachment_type_ids)
                slip.update({'input_line_ids': [Command.unlink(line.id) for line in lines_to_remove]})
            if slip.employee_id.salary_attachment_ids and slip.date_to:
                lines_to_remove = slip.input_line_ids.filtered(lambda x: x.input_type_id.id in attachment_type_ids)
                input_line_vals = [Command.unlink(line.id) for line in lines_to_remove]

                valid_attachments = slip.employee_id.salary_attachment_ids.filtered(
                    lambda a: a.state == 'open'
                        and a.date_start <= slip.date_to
                        and (not a.date_end or a.date_end >= slip.date_from)
                        and (not a.other_input_type_id.struct_ids or slip.struct_id in a.other_input_type_id.struct_ids)
                )
                # Only take deduction types present in structure
                for input_type_id, attachments in valid_attachments.grouped("other_input_type_id").items():
                    amount = attachments._get_active_amount()
                    name = ', '.join(description for description in attachments.mapped('description') if description)
                    input_line_vals.append(Command.create({
                        'name': name,
                        'amount': amount if not slip.credit_note else -amount,
                        'input_type_id': input_type_id.id,
                    }))
                slip.update({'input_line_ids': input_line_vals})

    @api.depends('input_line_ids.input_type_id', 'input_line_ids')
    def _compute_salary_attachment_ids(self):
        for slip in self:
            if not slip.input_line_ids and not slip.salary_attachment_ids:
                continue
            attachments = self.env['hr.salary.attachment']
            if slip.employee_id and slip.input_line_ids and slip.date_to:
                deduction_types = slip.input_line_ids.input_type_id.filtered("available_in_attachments").ids
                attachments = slip.employee_id.salary_attachment_ids.filtered(
                    lambda a: (
                        a.state == 'open'
                        and a.other_input_type_id.id in deduction_types
                        and a.date_start <= slip.date_to
                    )
                )
            slip.salary_attachment_ids = attachments

    @api.depends('salary_attachment_ids')
    def _compute_salary_attachment_count(self):
        for slip in self:
            slip.salary_attachment_count = len(slip.salary_attachment_ids)

    @api.depends('employee_id', 'state')
    def _compute_negative_net_to_report_display(self):
        activity_type = self.env.ref(
            'hr_payroll.mail_activity_data_hr_payslip_negative_net',
            raise_if_not_found=False
        ) or self.env['mail.activity.type']
        for payslip in self:
            if payslip.state == 'draft':
                payslips_to_report = self.env['hr.payslip'].search([
                    ('has_negative_net_to_report', '=', True),
                    ('employee_id', 'in', payslip.employee_id.ids),
                    ('credit_note', '=', False),
                ])
                payslip.negative_net_to_report_display = payslips_to_report
                payslip.negative_net_to_report_amount = payslips_to_report._get_line_values(['NET'], compute_sum=True)['NET']['sum']['total']
                payslip.negative_net_to_report_message = _(
                    'There are previous payslips with a negative amount for a total of %s to report.',
                    round(payslip.negative_net_to_report_amount, 2))
                if payslips_to_report and payslip.state == 'draft' and payslip.line_ids and payslip.version_id and (
                    not payslip.activity_ids.filtered(lambda a: a.activity_type_id == activity_type)
                ):
                    payslip.activity_schedule(
                        'hr_payroll.mail_activity_data_hr_payslip_negative_net',
                        summary=_('Previous Negative Payslip to Report'),
                        note=_('At least one previous negative net could be reported on this payslip for %s',
                                payslip.employee_id._get_html_link()),
                        user_id=payslip.version_id.hr_responsible_id.id or self.env.ref('base.user_admin').id)
            else:
                payslip.negative_net_to_report_display = False
                payslip.negative_net_to_report_amount = False
                payslip.negative_net_to_report_message = False

    @api.depends('related_payslip_ids')
    def _compute_related_payslip_count_count(self):
        for slip in self:
            slip.related_payslip_count = len(slip.related_payslip_ids)

    def _get_negative_net_input_type(self):
        self.ensure_one()
        return self.env.ref('hr_payroll.input_deduction')

    def action_report_negative_amount(self):
        self.ensure_one()
        deduction_input_type = self._get_negative_net_input_type()
        deduction_input_line = self.input_line_ids.filtered(lambda l: l.input_type_id == deduction_input_type)
        if deduction_input_line:
            deduction_input_line.amount += abs(self.negative_net_to_report_amount)
        else:
            self.write({'input_line_ids': [(0, 0, {
                'input_type_id': deduction_input_type.id,
                'amount': abs(self.negative_net_to_report_amount),
            })]})
            self.compute_sheet()
        self.env['hr.payslip'].search([
            ('has_negative_net_to_report', '=', True),
            ('employee_id', '=', self.employee_id.id),
            ('credit_note', '=', False),
        ]).write({'has_negative_net_to_report': False})
        self.activity_feedback(['hr_payroll.mail_activity_data_hr_payslip_negative_net'])

    def _compute_is_regular(self):
        for payslip in self:
            payslip.is_regular = payslip.struct_id.type_id.default_struct_id == payslip.struct_id

    @api.depends('employee_id.current_version_id', 'version_id.last_modified_date', 'date_from')
    def _compute_is_wrong_version(self):
        for payslip in self.filtered(lambda slip: slip.state in ("validated", "paid")):
            payslip.is_wrong_version = payslip.employee_id and payslip.version_id \
                                        and payslip.version_id != payslip.employee_id._get_version(date=payslip.date_from)
            payslip.has_wrong_data = payslip.version_id.last_modified_date > payslip.done_date

    def _is_invalid(self):
        self.ensure_one()
        if self.state not in ['validated', 'paid']:
            return _("This payslip is not validated. This is not a legal document.")
        return False

    @api.depends(lambda self: self._get_recomputing_fields())
    def _compute_line_ids(self):
        if not self.env.context.get("payslip_no_recompute"):
            return
        payslips = self.filtered(lambda p: p.line_ids and p.state == 'draft')
        for payslip in payslips:
            lines_vals = []
            if payslip.employee_id and payslip.version_id and payslip.date_from and payslip.date_to and payslip.struct_id:
                lines_vals = [(0, 0, line_vals) for line_vals in payslip._get_payslip_lines()]
            payslip.line_ids = [(5, 0, 0)] + lines_vals

    def _get_recomputing_fields(self):
        return [
            'employee_id', 'version_id', 'struct_id',
            'date_from', 'date_to', 'worked_days_line_ids',
            'input_line_ids'
        ]

    @api.depends('line_ids.total', 'struct_id.rule_ids.appears_on_employee_cost_dashboard')
    def _compute_basic_net(self):
        line_values = (self._origin)._get_line_values(['BASIC', 'GROSS', 'NET'])
        employer_cost_codes = set(self.env['hr.salary.rule'].search([
            ('appears_on_employee_cost_dashboard', '=', True)
        ]).mapped('code'))
        employer_cost_values = {}
        if employer_cost_codes:
            employer_cost_values = (self._origin)._get_line_values(employer_cost_codes)
        for payslip in self:
            employer_cost_total = 0.0
            payslip_employer_codes = payslip.struct_id.rule_ids.filtered(
                'appears_on_employee_cost_dashboard'
            ).mapped('code')
            for code in payslip_employer_codes:
                employer_cost_total += employer_cost_values[code][payslip._origin.id]['total']
            payslip.write({
                'basic_wage': line_values['BASIC'][payslip._origin.id]['total'],
                'gross_wage': line_values['GROSS'][payslip._origin.id]['total'],
                'net_wage': line_values['NET'][payslip._origin.id]['total'],
                'employer_cost': employer_cost_total,
            })

    @api.depends('worked_days_line_ids.number_of_hours', 'worked_days_line_ids.is_paid')
    def _compute_worked_hours(self):
        for payslip in self:
            payslip.sum_worked_hours = sum(line.number_of_hours for line in payslip.worked_days_line_ids)

    def _get_regular_worked_hours(self):
        # To be overridden by localization modules. Used for the amount computation for each worked days type.
        self.ensure_one()
        return self.sum_worked_hours

    def _compute_is_superuser(self):
        self.is_superuser = self.env.user._is_superuser() and self.env.user.has_group('base.group_no_one')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        if any(payslip.date_from > payslip.date_to for payslip in self):
            raise ValidationError(_("Payslip 'Date From' must be earlier than 'Date To'."))

    def _record_attachment_payment(self, attachments, slip_lines):
        self.ensure_one()
        sign = -1 if self.credit_note else 1
        amount = sum(sl.total for sl in slip_lines) if not all(attachments.other_input_type_id.mapped("is_quantity")) else sum(sl.quantity for sl in slip_lines)
        attachments.record_payment(sign * abs(amount))

    def write(self, vals):
        res = super().write(vals)

        if 'state' in vals and vals['state'] == 'paid':
            # Register payment in Salary Attachments
            # NOTE: Since we combine multiple attachments on one input line, it's not possible to compute
            #  how much per attachment needs to be taken record_payment will consume monthly payments (child_support) before other attachments
            for slip in self.filtered(lambda r: r.salary_attachment_ids):
                for deduction_codes, attachments in slip.salary_attachment_ids.grouped(lambda x: x.other_input_type_id.code).items():
                    # Use the amount from the computed value in the payslip lines not the input
                    salary_lines = slip.line_ids.filtered(lambda r: r.code in deduction_codes)
                    if not attachments or not salary_lines:
                        continue
                    slip._record_attachment_payment(attachments, salary_lines)
        return res

    def action_draft_linked_entries(self):
        work_entries = self.env['hr.work.entry'].search(
                Domain('employee_id', '=', self.employee_id.ids)
                & Domain('date', '>=', min(self.mapped('date_from')))
                & Domain('date', '<=', max(self.mapped('date_to')))
                & Domain('state', '=', 'validated')
            )
        linked_entries = self.env['hr.work.entry']
        similar_payslips = self._get_similar_payslips()
        for regular_payslip in self:
            payslip_start = regular_payslip.date_from
            payslip_end = regular_payslip.date_to
            key = (regular_payslip.employee_id.id, regular_payslip.struct_id.id, payslip_start, payslip_end)
            duplicates = similar_payslips[key].filtered(lambda dup: dup.id != regular_payslip.id)
            if duplicates:
                continue
            linked_entries |= work_entries.filtered(
                lambda entry: entry.employee_id == regular_payslip.employee_id
                              and payslip_start <= entry.date <= payslip_end
                              and not entry.has_payslip)

        if linked_entries:
            linked_entries.action_set_to_draft()

    def action_payslip_draft(self):
        self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'hr.payslip'),
            ('res_id', 'in', self.ids),
            ('res_field', '=', 'payment_report'),
        ]).unlink()
        self.write({
            'payment_report': False,
            'payment_report_filename': False,
            'payment_report_date': False,
            'state': 'draft'
        })
        self.action_draft_linked_entries()
        return True

    def _get_pdf_reports(self):
        default_report = self.env.ref('hr_payroll.action_report_payslip')
        result = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in self:
            if not payslip.struct_id or not payslip.struct_id.report_id:
                result[default_report] |= payslip
            else:
                result[payslip.struct_id.report_id] |= payslip
        return result

    def _get_email_template(self):
        return self.env.ref(
            'hr_payroll.mail_template_new_payslip', raise_if_not_found=False
        )

    def _generate_pdf(self):
        mapped_reports = self._get_pdf_reports()
        attachments_vals_list = []
        generic_name = _("Payslip")
        for report, payslips in mapped_reports.items():
            for payslip in payslips:
                pdf_content, dummy = self.env['ir.actions.report'].sudo().with_context(lang=payslip.employee_id.lang or self.env.lang)._render_qweb_pdf(report, payslip.id)
                if report.print_report_name:
                    pdf_name = safe_eval(report.print_report_name, {'object': payslip})
                else:
                    pdf_name = generic_name
                attachments_vals_list.append({
                    'name': pdf_name,
                    'type': 'binary',
                    'raw': pdf_content,
                    'res_model': payslip._name,
                    'res_id': payslip.id
                })

        self.env['ir.attachment'].sudo().create(attachments_vals_list)
        # Send email to employees (after attachment is created to include it in the mail by other bridge module)
        for payslips in mapped_reports.values():
            for payslip in payslips:
                template = payslip._get_email_template()
                if template:
                    template.send_mail(payslip.id, email_layout_xmlid='mail.mail_notification_light')

    def _filter_out_of_versions_payslips(self):
        return self.filtered(lambda p:  p.version_id and p.date_from and p.date_to and not p.version_id._is_overlapping_period(p.date_from, p.date_to) and not p.is_refund_payslip)

    def action_payslip_done(self):
        if any(slip.state == 'cancel' for slip in self):
            raise ValidationError(_("You can't confirm cancelled payslips."))
        if self.filtered('error_count'):
            raise ValidationError(self._get_error_message())
        self.write({
            'state': 'validated',
            'done_date': fields.Datetime.now(),
        })

        line_values = self._get_line_values(['NET'])

        self.filtered(lambda p: not p.credit_note and line_values['NET'][p.id]['total'] < 0).write({'has_negative_net_to_report': True})
        # Validate work entries for regular payslips (exclude end of year bonus, ...)
        regular_payslips = self.filtered(lambda p: p.struct_id.type_id.default_struct_id == p.struct_id)
        work_entries_domain = Domain.OR([
            [
                ('date', '<=', regular_payslip.date_to),
                ('date', '>=', regular_payslip.date_from),
                ('employee_id', '=', regular_payslip.employee_id.id)
            ] for regular_payslip in regular_payslips
        ])
        work_entries = self.env['hr.work.entry'].search(work_entries_domain)
        if work_entries:
            work_entries.action_validate()

        if self.env.context.get('payslip_generate_pdf'):
            if self.env.context.get('payslip_generate_pdf_direct'):
                self._generate_pdf()
            else:
                self.write({'queued_for_pdf': True})
                payslip_cron = self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs', raise_if_not_found=False)
                if payslip_cron:
                    payslip_cron._trigger()

    def action_validate(self):
        self.filtered(lambda slip: slip.state == 'draft' and not slip.line_ids).compute_sheet()
        self.filtered(lambda slip: slip.state == 'draft').action_payslip_done()

    def action_payslip_cancel(self):
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_manager') \
            and self.filtered(lambda slip: slip.state == 'validated'):
            raise UserError(_("Cannot cancel a payslip that is validated."))
        self.write({'state': 'cancel'})
        self.action_draft_linked_entries()

    def action_payslip_paid(self):
        if any(slip.state not in ['validated', 'paid'] for slip in self):
            raise UserError(_('Cannot mark payslip as paid if not confirmed.'))
        if self.filtered('error_count'):
            raise ValidationError(self._get_error_message())
        self.filtered(lambda p: p.state != 'paid').write({
            'state': 'paid',
            'paid_date': fields.Date.today(),
        })

    def action_payslip_payment_report(self, export_format='csv'):
        self.ensure_one()
        if len(self.payslip_run_id) > 1:
            raise UserError(_('The selected payslips should be linked to the same batch'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.payment.report.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_payslip_ids': self.ids,
                'default_payslip_run_id': self.payslip_run_id.id,
                'default_export_format': export_format,
            },
        }

    def action_payslip_unpaid(self):
        if any(slip.state != 'paid' for slip in self):
            raise UserError(_('You cannot cancel the payment if the payslip has not been paid.'))
        self.write({'state': 'validated'})
        self.payslip_run_id.write({'state': '02_close'})

    def action_open_work_entries(self):
        self.ensure_one()
        return self.employee_id.action_open_work_entries(initial_date=self.date_from)

    def action_open_salary_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Salary Adjustments'),
            'res_model': 'hr.salary.attachment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.salary_attachment_ids.ids)],
        }

    def action_keep_wrong_version(self):
        self.keep_wrong_version = True

    def action_adjust_payslip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Payslip Correction'),
            'res_model': 'hr.payslip.correction.wizard',
            'view_mode': 'form',
            'view_id': 'hr_payslip_correction_wizard_form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_employee_id': self.employee_id.id,
                'default_payslip_id': self.id,
            },
        }

    def action_open_related_payslips(self):
        return {
                'name': self.env._("Related Payslip"),
                'res_model': 'hr.payslip',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'view_mode': 'list, form',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('id', 'in', self.related_payslip_ids.ids)],
        }

    def _get_payslips_action(self):
        formview_ref = self.env.ref('hr_payroll.view_hr_payslip_form', False)
        listview_ref = self.env.ref('hr_payroll.view_hr_payslip_tree', False)
        return {
                'type': 'ir.actions.act_window',
                'name': self.env._("Refund Payslip"),
                'res_model': 'hr.payslip',
                'target': 'current',
                'view_mode': 'list,form',
                'views': [(listview_ref.id, 'list'), (formview_ref.id, 'form')],
                'domain': [('id', 'in', self.ids)],
            }

    def _action_refund_payslips(self):
        reverted_payslips = self.env['hr.payslip']
        for payslip in self:
            reverted_payslip = payslip.copy({
                'credit_note': True,
                'name': self.env._('Refund: %(payslip)s', payslip=payslip.name),
                'edited': True,
                'state': 'draft',
                'origin_payslip_id': payslip.id,
                'is_refund_payslip': True,
            })
            for wd in reverted_payslip.worked_days_line_ids:
                wd.number_of_hours = -wd.number_of_hours
                wd.number_of_days = -wd.number_of_days
                wd.amount = -wd.amount
            for line in reverted_payslip.line_ids:
                line.amount = -line.amount
                line.total = -line.total
            reverted_payslips |= reverted_payslip
            payslip.message_post(
                body=self.env._('This is a refunded payslip.\nFind the refund under this name: %(payslip)s', payslip=reverted_payslip.name)
            )
            payslip.is_refunded = True
        return reverted_payslips

    def _action_correct_payslips(self):
        corrected_payslips_values = []
        for payslip in self:
            corrected_name = self.env._('Correction: %(payslip)s', payslip=payslip.name)
            corrected_payslips_values.append({
                'name': corrected_name,
                'origin_payslip_id': payslip.id,
                'employee_id': payslip.employee_id.id,
                'version_id': payslip.employee_id._get_version(date=payslip.date_from).id,
                'date_from': payslip.date_from,
                'date_to': payslip.date_to,
            })
            payslip.message_post(
                body=self.env._('This is a corrected payslip.\nFind the correction under this name: %(payslip)s', payslip=corrected_name))
            payslip.is_corrected = True
        corrected_payslips = self.env['hr.payslip'].create(corrected_payslips_values)
        corrected_payslips.compute_sheet()
        return corrected_payslips

    def refund_sheet(self):
        reverted_payslips = self._action_refund_payslips()
        return (self | reverted_payslips)._get_payslips_action()

    def correct_sheet(self):
        reverted_payslips = self._action_refund_payslips()
        corrected_payslips = self._action_correct_payslips()
        return (self | corrected_payslips | reverted_payslips)._get_payslips_action()

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft_or_cancel(self):
        if any(payslip.state not in ('draft', 'cancel') for payslip in self):
            raise UserError(_(
                "Oops! Only draft and cancelled payslips can be deleted without causing any chaos. We can't "
                "take back our dedicated employees' hard-earned cash!"
            ))
        self.action_draft_linked_entries()

    def compute_sheet(self):
        payslips = self.filtered(lambda slip: slip.state == 'draft')
        if payslips.filtered('error_count'):
            self._get_error_message()
        # delete old payslip lines
        payslips.line_ids.unlink()
        # this guarantees consistent results
        self.env.flush_all()
        today = fields.Date.today()
        for payslip in payslips:
            payslip.write({
                'state': 'draft',
                'compute_date': today
            })
        self.env['hr.payslip.line'].create(payslips._get_payslip_lines())
        if any(payslips.mapped('ytd_computation')):
            self._compute_worked_days_ytd()
        return True

    def action_refresh_from_work_entries(self):
        # Refresh the whole payslip in case the HR has modified some work entries
        # after the payslip generation
        if any(p.state != 'draft' for p in self):
            raise UserError(_('The payslips should be in Draft or Waiting state.'))
        payslips = self.filtered(lambda p: not p.edited)
        payslips._compute_payslip_properties()
        payslips.mapped('worked_days_line_ids').unlink()
        payslips.mapped('line_ids').unlink()
        payslips._compute_worked_days_line_ids()
        payslips.compute_sheet()

    def action_move_to_off_cycle(self):
        self.payslip_run_id = False

    def _round_days(self, work_entry_type, days):
        if work_entry_type.round_days != 'NO':
            precision_rounding = 0.5 if work_entry_type.round_days == "HALF" else 1
            day_rounded = float_round(days, precision_rounding=precision_rounding, rounding_method=work_entry_type.round_days_type)
            return day_rounded
        return days

    @api.model
    def _get_attachment_types(self):
        input_types = self.env['hr.payslip.input.type'].search([('available_in_attachments', '=', True)])
        return {input_type.code: input_type for input_type in input_types}

    def _get_worked_day_lines_hours_per_day(self):
        self.ensure_one()
        calendar = self.version_id.resource_calendar_id or self.employee_id.resource_calendar_id or self.company_id.resource_calendar_id
        return calendar.hours_per_day

    def _get_worked_day_lines_hours_per_week(self):
        self.ensure_one()
        calendar = self.version_id.resource_calendar_id or self.employee_id._get_calendars()[self.employee_id.id]
        return calendar.hours_per_week

    def _get_out_of_contract_calendar(self):
        self.ensure_one()
        return self.version_id.resource_calendar_id or self.employee_id.resource_calendar_id or self.company_id.resource_calendar_id

    def _get_worked_day_lines_values(self, domain=None):
        self.ensure_one()
        res = []
        hours_per_day = self._get_worked_day_lines_hours_per_day()
        work_hours = self.version_id.get_work_hours(self.date_from, self.date_to, domain=domain)
        work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
        biggest_work = work_hours_ordered[-1][0] if work_hours_ordered else 0
        add_days_rounding = 0
        for work_entry_type_id, hours in work_hours_ordered:
            work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
            days = round(hours / hours_per_day, 5) if hours_per_day else 0
            if work_entry_type_id == biggest_work:
                days += add_days_rounding
            day_rounded = self._round_days(work_entry_type, days)
            add_days_rounding += (days - day_rounded)
            attendance_line = {
                'sequence': work_entry_type.sequence,
                'work_entry_type_id': work_entry_type_id,
                'number_of_days': day_rounded,
                'number_of_hours': hours,
            }
            res.append(attendance_line)

        # Sort by Work Entry Type sequence
        work_entry_type = self.env['hr.work.entry.type']
        return sorted(res, key=lambda d: work_entry_type.browse(d['work_entry_type_id']).sequence)

    def _get_worked_day_lines(self, domain=None, check_out_of_version=True):
        """
        :returns: a list of dict containing the worked days values that should be applied for the given payslip
        """
        res = []
        self.ensure_one()
        version = self.version_id
        res = self._get_worked_day_lines_values(domain=domain)
        if not check_out_of_version:
            return res

        # If the version doesn't cover the whole month, create
        # worked_days lines to adapt the wage accordingly
        out_days, out_hours = 0, 0
        reference_calendar = self._get_out_of_contract_calendar()
        if self.date_from < version.date_start:
            start = fields.Datetime.to_datetime(self.date_from)
            stop = fields.Datetime.to_datetime(version.date_start) + relativedelta(days=-1, hour=23, minute=59)
            out_time = reference_calendar.get_work_duration_data(start, stop, compute_leaves=False, domain=['|', ('work_entry_type_id', '=', False), ('work_entry_type_id.is_leave', '=', False)])
            out_days += out_time['days']
            out_hours += out_time['hours']
        if version.date_end and version.date_end < self.date_to:
            start = fields.Datetime.to_datetime(version.date_end) + relativedelta(days=1)
            stop = fields.Datetime.to_datetime(self.date_to) + relativedelta(hour=23, minute=59)
            out_time = reference_calendar.get_work_duration_data(start, stop, compute_leaves=False, domain=['|', ('work_entry_type_id', '=', False), ('work_entry_type_id.is_leave', '=', False)])
            out_days += out_time['days']
            out_hours += out_time['hours']

        work_entry_type = self.env.ref('hr_work_entry.hr_work_entry_type_out_of_contract', raise_if_not_found=False)
        if work_entry_type and (out_days or out_hours):
            res.append({
                'sequence': work_entry_type.sequence,
                'work_entry_type_id': work_entry_type.id,
                'number_of_days': out_days,
                'number_of_hours': out_hours,
            })
        return res

    @property
    def paid_amount(self):
        self.ensure_one()
        return self._get_paid_amount()

    @property
    def is_outside_contract(self):
        self.ensure_one()
        if self.env.context.get('salary_simulation'):
            return False
        return self._is_outside_contract_dates()

    def _rule_parameter(self, code, reference_date=False):
        self.ensure_one()
        if reference_date:
            return self.env['hr.rule.parameter']._get_parameter_from_code(code, reference_date)
        else:
            return self.env['hr.rule.parameter']._get_parameter_from_code(code, self.date_to)

    def _sum(self, code, from_date, to_date=None):
        if to_date is None:
            to_date = fields.Date.today()
        self.env.cr.execute("""
            SELECT sum(pl.total)
            FROM hr_payslip as hp, hr_payslip_line as pl
            WHERE hp.employee_id = %s
            AND hp.state in ('validated', 'paid')
            AND hp.date_from >= %s
            AND hp.date_to <= %s
            AND hp.id = pl.slip_id
            AND pl.code = %s""", (self.employee_id.id, from_date, to_date, code))
        res = self.env.cr.fetchone()
        return res and res[0] or 0.0

    def _sum_category(self, code, from_date, to_date=None):
        self.ensure_one()
        if to_date is None:
            to_date = fields.Date.today()

        self.env['hr.payslip'].flush_model(['employee_id', 'state', 'date_from', 'date_to'])
        self.env['hr.payslip.line'].flush_model(['total', 'slip_id', 'salary_rule_id'])
        self.env['hr.salary.rule.category'].flush_model(['code'])

        self.env.cr.execute("""
            SELECT sum(pl.total)
            FROM
                hr_payslip as hp,
                hr_payslip_line as pl,
                hr_salary_rule_category as rc,
                hr_salary_rule as sr
            WHERE hp.employee_id = %s
            AND hp.state in ('validated', 'paid')
            AND hp.date_from >= %s
            AND hp.date_to <= %s
            AND hp.id = pl.slip_id
            AND sr.id = pl.salary_rule_id
            AND rc.id = sr.category_id
            AND rc.code = %s""", (self.employee_id.id, from_date, to_date, code))
        res = self.env.cr.fetchone()
        return res and res[0] or 0.0

    def _sum_worked_days(self, code, from_date, to_date=None):
        self.ensure_one()
        if to_date is None:
            to_date = fields.Date.today()

        query = """
            SELECT sum(hwd.amount)
            FROM hr_payslip hp, hr_payslip_worked_days hwd, hr_work_entry_type hwet
            WHERE hp.state in ('validated', 'paid')
            AND hp.id = hwd.payslip_id
            AND hwet.id = hwd.work_entry_type_id
            AND hp.employee_id = %(employee)s
            AND hp.date_to <= %(stop)s
            AND hwet.code = %(code)s
            AND hp.date_from >= %(start)s"""

        self.env.cr.execute(query, {
            'employee': self.employee_id.id,
            'code': code,
            'start': from_date,
            'stop': to_date})
        res = self.env.cr.fetchone()
        return res[0] if res else 0.0

    def _get_base_local_dict(self):
        return {
            'float_round': float_round,
            'float_compare': float_compare,
            'relativedelta': safe_eval_dateutil.relativedelta.relativedelta,
            'ceil': math.ceil,
            'floor': math.floor,
            'UserError': UserError,
            'date': safe_eval_datetime.date,
            'datetime': safe_eval_datetime.datetime,
            'defaultdict': defaultdict,
        }

    def _get_localdict(self):
        self.ensure_one()
        # Check for multiple inputs of the same type and keep a copy of
        # them because otherwise they are lost when building the dict
        same_type_input_lines = defaultdict(lambda x: self.env['hr.payslip.input'])
        input_line_ids_by_code = self.input_line_ids.grouped('code')
        for code, input_lines in input_line_ids_by_code.items():
            if len(input_lines) > 1:
                same_type_input_lines[code] = input_lines

        employee_properties = dict(self.version_id.payroll_properties)
        payslip_properties = dict(self.payslip_properties)
        employee_properties.update(payslip_properties)

        localdict = {
            **self._get_base_local_dict(),
            **{
                'categories': DefaultDictPayroll(lambda: 0),
                'rules': DefaultDictPayroll(lambda: dict(total=0, amount=0, quantity=0)),
                'payslip': self,
                'worked_days': {line.code: line for line in self.worked_days_line_ids if line.code},
                'property_inputs': {self.env['hr.salary.rule'].browse(int(rule_id)).id: float(value) for rule_id, value in employee_properties.items()},
                'inputs': {line.code: line for line in self.input_line_ids if line.code},
                'employee': self.employee_id,
                'version': self.version_id,
                'result_rules': DefaultDictPayroll(lambda: dict(total=0, amount=0, quantity=0, rate=0, ytd=0)),
                'same_type_input_lines': same_type_input_lines,
            }
        }
        for code, input_lines in same_type_input_lines.items():
            input_line_ids = input_lines.ids
            localdict['inputs'][code] = self.__get_aggregator_hr_payslip_input_model()(
                env=self.env, ids=input_line_ids, prefetch_ids=input_line_ids,
            )
        return localdict

    def _get_payslip_line_total(self, amount, quantity, rate, rule):
        self.ensure_one()
        return amount * quantity * rate / 100.0

    def _get_last_ytd_payslips(self):
        if not self:
            return self

        earliest_date_to = min(self.mapped('date_to'))
        earliest_ytd_date_to = min(
            company.get_last_ytd_reset_date(earliest_date_to) for company in self.company_id
        )
        ytd_payslips_grouped = self.env['hr.payslip']._read_group(
            domain=[
                ('employee_id', 'in', self.employee_id.ids),
                ('struct_id', 'in', self.struct_id.ids),
                ('ytd_computation', '=', True),
                ('date_to', '>=', earliest_ytd_date_to),
                ('date_to', '<=', max(self.mapped('date_to'))),
                ('state', 'in', ['validated', 'paid']),
            ],
            groupby=['employee_id', 'struct_id'],
            aggregates=['id:recordset']
        )

        ytd_payslips_sorted = defaultdict(lambda: self.env['hr.payslip'])
        for employee_id, struct_id, payslips in ytd_payslips_grouped:
            ytd_payslips_sorted[(employee_id, struct_id)] = payslips.sorted(
                key=lambda p: p.date_to, reverse=True
            )

        last_ytd_payslips = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in self:
            last_payslips = ytd_payslips_sorted[(payslip.employee_id, payslip.struct_id)].filtered(
                lambda p: p.date_to <= payslip.date_to
            )
            if last_payslips and last_payslips[0].date_to >=\
                    payslip.company_id.get_last_ytd_reset_date(payslip.date_to):
                last_ytd_payslips[payslip] = last_payslips[0]

        return last_ytd_payslips

    def _get_payslip_lines(self):
        def get_rule_name(localdict, rule):
            if localdict['result_name']:
                return localdict['result_name']
            if rule.amount_select == "input"\
                and rule.amount_other_input_id.code in localdict['inputs']\
                    and (name := localdict['inputs'][rule.amount_other_input_id.code].name):
                return name
            return rule.name

        line_vals = []

        if any(self.mapped('ytd_computation')):
            last_ytd_payslips = self._get_last_ytd_payslips()
            code_set = set(self.struct_id.rule_ids.mapped('code'))
        else:
            last_ytd_payslips = defaultdict(lambda: self.env['hr.payslip'])
            code_set = set()
        ytd_payslips = reduce(
            lambda ytd_payslips, payslip: ytd_payslips | payslip, last_ytd_payslips.values(),
            self.env['hr.payslip']
        )

        line_values = ytd_payslips._get_line_values(code_set, ['ytd'])

        for payslip in self:
            if lang := payslip.employee_id.lang:
                # /!\ Don't remove /!\ ensure that the employee will receive their payslip in their language.
                payslip = payslip.with_context(lang=lang)

            localdict = self.env.context.get('force_payslip_localdict', payslip._get_localdict())
            result_rules_dict = localdict['result_rules']

            blacklisted_rule_ids = self.env.context.get('prevent_payslip_computation_line_ids', [])

            result = {}
            for rule in sorted(payslip.struct_id.rule_ids, key=lambda x: x.sequence):
                if rule.id in blacklisted_rule_ids:
                    continue
                localdict.update({
                    'result': None,
                    'result_qty': 1.0,
                    'result_rate': 100,
                    'result_name': False
                })
                if rule._satisfy_condition(localdict):
                    if rule.code in localdict['same_type_input_lines']:
                        for multi_line_rule in localdict['same_type_input_lines'][rule.code]:
                            localdict['inputs'][rule.code] = multi_line_rule
                            amount, qty, rate = rule._compute_rule(localdict)
                            tot_rule = payslip._get_payslip_line_total(amount, qty, rate, rule)
                            ytd = line_values[rule.code][last_ytd_payslips[payslip].id]['ytd'] + tot_rule

                            result_rules_dict[rule.code]['total'] += tot_rule
                            result_rules_dict[rule.code]['amount'] += tot_rule
                            result_rules_dict[rule.code]['quantity'] = 1
                            result_rules_dict[rule.code]['rate'] = 100
                            result_rules_dict[rule.code]['ytd'] = ytd

                            localdict = rule.category_id._sum_salary_rule_category(
                                localdict, tot_rule)
                            line_vals.append({
                                'sequence': rule.sequence,
                                'code': rule.code,
                                'name':  get_rule_name(localdict, rule),
                                'salary_rule_id': rule.id,
                                'version_id': localdict['version'].id,
                                'employee_id': localdict['employee'].id,
                                'amount': amount,
                                'quantity': qty,
                                'rate': rate,
                                'total': tot_rule,
                                'slip_id': payslip.id,
                                'ytd': ytd,
                            })
                        input_line_ids = localdict['same_type_input_lines'][rule.code].ids
                        localdict['inputs'][rule.code] = self.__get_aggregator_hr_payslip_input_model()(
                            env=self.env, ids=input_line_ids, prefetch_ids=input_line_ids,
                        )
                    else:
                        amount, qty, rate = rule._compute_rule(localdict)
                        #check if there is already a rule computed with that code
                        previous_amount = localdict.get(rule.code, 0.0)
                        #set/overwrite the amount computed for this rule in the localdict
                        tot_rule = payslip._get_payslip_line_total(amount, qty, rate, rule)
                        ytd = line_values[rule.code][last_ytd_payslips[payslip].id]['ytd'] + tot_rule
                        localdict[rule.code] = tot_rule
                        result_rules_dict[rule.code] = {
                            'total': tot_rule, 'amount': amount, 'quantity': qty, 'rate': rate, 'ytd': ytd
                        }
                        # sum the amount for its salary category
                        localdict = rule.category_id._sum_salary_rule_category(localdict, tot_rule - previous_amount)
                        # create/overwrite the rule in the temporary results
                        result[rule.code] = {
                            'sequence': rule.sequence,
                            'code': rule.code,
                            'name': get_rule_name(localdict, rule),
                            'salary_rule_id': rule.id,
                            'version_id': localdict['version'].id,
                            'employee_id': localdict['employee'].id,
                            'amount': amount,
                            'quantity': qty,
                            'rate': rate,
                            'total': tot_rule,
                            'slip_id': payslip.id,
                            'ytd': ytd,
                        }
            line_vals += list(result.values())
        return line_vals

    def _compute_worked_days_ytd(self):
        last_ytd_payslips = self._get_last_ytd_payslips()
        ytd_payslips = reduce(
            lambda ytd_payslips, payslip: ytd_payslips | payslip, last_ytd_payslips.values(),
            self.env['hr.payslip']
        )

        code_set = set(self.worked_days_line_ids.mapped('code'))
        worked_days_line_values = ytd_payslips._get_worked_days_line_values(code_set, ['ytd'])

        for payslip in self:
            for worked_days in payslip.worked_days_line_ids:
                worked_days.ytd = worked_days_line_values[worked_days.code][
                    last_ytd_payslips[payslip].id
                ]['ytd'] + worked_days.amount

    @api.depends('employee_id')
    def _compute_company_id(self):
        for slip in self.filtered(lambda p: p.employee_id):
            slip.company_id = slip.employee_id.company_id

    @api.depends('employee_id', 'date_from')
    def _compute_version_id(self):
        for slip in self:
            slip.version_id = slip.employee_id._get_version(slip.date_from) if slip.employee_id else False

    @api.depends('version_id')
    def _compute_struct_id(self):
        for slip in self.filtered(lambda p: not p.struct_id):
            slip.struct_id = slip.version_id.structure_type_id.default_struct_id\
                or slip.employee_id.version_id.structure_type_id.default_struct_id

    def _get_period_name(self, cache):
        self.ensure_one()
        period_name = '%s - %s' % (
            self._format_date_cached(cache, self.date_from),
            self._format_date_cached(cache, self.date_to))
        if self.is_wrong_duration:
            return period_name

        start_date = self.date_from
        end_date = self.date_to
        lang = self.employee_id.lang or self.env.user.lang
        week_start = self.env["res.lang"]._get_data(code=lang).week_start
        schedule = self.version_id.schedule_pay or self.version_id.structure_type_id.default_schedule_pay
        if schedule == 'monthly':
            period_name = self._format_date_cached(cache, start_date, "MMMM Y")
        elif schedule == 'quarterly':
            current_year_quarter = math.ceil(start_date.month / 3)
            period_name = _("Quarter %(quarter)s of %(year)s", quarter=current_year_quarter, year=start_date.year)
        elif schedule == 'semi-annually':
            year_half = start_date.replace(day=1, month=6)
            is_first_half = start_date < year_half
            period_name = _("1st semester of %s", start_date.year)\
                if is_first_half\
                else _("2nd semester of %s", start_date.year)
        elif schedule == 'annually':
            period_name = start_date.year
        elif schedule == 'weekly':
            wk_num = start_date.strftime('%U') if week_start == '7' else start_date.strftime('%W')
            period_name = _('Week %(week_number)s of %(year)s', week_number=wk_num, year=start_date.year)
        elif schedule == 'bi-weekly':
            week = int(start_date.strftime("%U") if week_start == '7' else start_date.strftime("%W"))
            first_week = week - 1 + week % 2
            period_name = _("Weeks %(week)s and %(week1)s of %(year)s",
                week=first_week, week1=first_week + 1, year=start_date.year)
        elif schedule == 'bi-monthly':
            start_date_string = self._format_date_cached(cache, start_date, "MMMM Y")
            end_date_string = self._format_date_cached(cache, end_date, "MMMM Y")
            period_name = _("%(start_date_string)s and %(end_date_string)s", start_date_string=start_date_string, end_date_string=end_date_string)
        return period_name

    def _format_date_cached(self, cache, date, date_format=False):
        key = (date, date_format)
        if key not in cache:
            lang = self.employee_id.lang or self.env.user.lang
            cache[key] = format_date(env=self.env, value=date, lang_code=lang, date_format=date_format)
        return cache[key]

    @api.depends('employee_id.legal_name', 'employee_id.lang', 'struct_id', 'date_from', 'date_to')
    def _compute_name(self):
        formated_date_cache = {}
        for slip in self.filtered(lambda p: p.employee_id and p.date_from and p.date_to):
            lang = slip.employee_id.lang or self.env.user.lang
            context = {'lang': lang}
            payslip_name = slip.struct_id.payslip_name or _('Salary Slip')
            del context

            slip.name = '%(payslip_name)s - %(employee_name)s - %(dates)s' % {
                'payslip_name': payslip_name,
                'employee_name': slip.employee_id.legal_name,
                'dates': slip._get_period_name(formated_date_cache),
            }

    @api.model
    def _issues_dependencies(self):
        return [
            'state', 'date_to', 'date_from', 'employee_id',
            'version_id', 'version_id.contract_date_start', 'version_id.contract_date_end', 'version_id.schedule_pay',
            'struct_id', 'version_id.structure_type_id.default_schedule_pay',
            'company_id', 'payslip_run_id.company_id',
            'employee_id.bank_account_ids', 'employee_id.bank_account_ids.allow_out_payment',
        ]

    def _get_errors_by_slip(self):
        by_state = self.grouped('state')
        draft_slips = by_state.get('draft', self.env['hr.payslip'])
        errors_by_slip = {slip: [] for slip in self}
        for slip in draft_slips._filter_out_of_versions_payslips():
            errors_by_slip[slip].append({
                'message': _('No running contract over payslip period'),
                'action_text': _("Contract"),
                'action': slip.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    target='new',
                    context={**self.env.context, 'version_id': slip.version_id.id}
                ),
                'level': 'danger',
            })
        for slip in draft_slips.filtered(lambda slip: slip.payslip_run_id and slip.company_id != slip.payslip_run_id.company_id):
            errors_by_slip[slip].append({
                'message': _("The payslip's company doesn't match the batch's"),
                'action_text': _('Batch'),
                'action': slip.payslip_run_id._get_records_action(),
                'level': 'danger',
            })
        return errors_by_slip

    def _get_warnings_by_slip(self):
        similar_payslips = self._get_similar_payslips()
        warnings_by_slip = {slip: [] for slip in self}

        for slip in self.filtered(lambda s: (
            s.state in ['draft', 'validated'] and s.date_from and s.date_to
        )):
            warnings = []
            if slip.struct_id.use_worked_day_lines \
                    and (slip.version_id.schedule_pay or slip.version_id.structure_type_id.default_schedule_pay) \
                    and slip.date_from \
                    and slip.date_from + slip._get_schedule_timedelta() != slip.date_to:
                warnings.append({
                    'message': _("The duration of the payslip is not accurate according to the structure type."),
                    'level': 'warning',
                })

            if slip.employee_id and slip.struct_id and slip.date_from and slip.date_to:
                key = (slip.employee_id.id, slip.struct_id.id, slip.date_from, slip.date_to)
                duplicates = similar_payslips[key].filtered(lambda dup: dup.id != slip.id)
                # Ignore duplicate warning if this slip is a refund of the original
                if duplicates:
                    related_payslips = self.env['hr.payslip']
                    if slip.origin_payslip_id:
                        related_payslips |= slip.origin_payslip_id | slip.origin_payslip_id.related_payslip_ids
                    if slip.related_payslip_ids:
                        related_payslips |= slip.related_payslip_ids
                    duplicates -= related_payslips

                if duplicates:
                    warnings.append({
                        'message': _("Similar payslips found"),
                        'action_text': _('Duplicate(s)'),
                        'action': duplicates._get_records_action(),
                        'level': 'warning',
                    })
            warnings_by_slip[slip] = warnings

        # Payment report related errors
        for employee_banks, slips in self.filtered(
            lambda ps: ps.state == 'validated'
        ).grouped(
            lambda ps: ps.employee_id.bank_account_ids
        ).items():
            if not employee_banks:
                for slip in slips:
                    warnings_by_slip[slip].append({
                        'message': _("Missing bank account on employee"),
                        'action_text': _('Employee'),
                        'action': slip.employee_id._get_records_action(),
                        'level': 'warning',
                    })
            elif any(not b.allow_out_payment for b in employee_banks):
                warning = {
                    'message': _("Untrusted bank accounts"),
                    'action_text': _('Bank Accounts'),
                    'action': employee_banks._get_records_action(),
                    'level': 'warning',
                }
                for slip in slips:
                    warnings_by_slip[slip].append(warning)
        return warnings_by_slip

    @api.depends(lambda self: self._issues_dependencies())
    def _compute_issues(self):
        errors_by_slip = self._get_errors_by_slip()
        warnings_by_slip = self._get_warnings_by_slip()

        for slip in self:
            warnings = warnings_by_slip[slip]
            errors = errors_by_slip[slip]
            slip.warning_count = len(warnings)
            slip.error_count = len(errors)
            if not errors and not warnings:
                slip.issues = {}
            else:
                slip.issues = dict(enumerate(errors + warnings))

    def _get_error_message(self):
        if len(self) == 1:
            return '\n'.join([
                f' • {issue["message"]}'
                for issue in self.issues.values() if issue['level'] == 'danger'
            ])
        return '\n'.join([
            f' • {slip.name}: {issue["message"]}'
            for slip in self
            for issue in (slip.issues or {}).values() if issue['level'] == 'danger'
        ])

    @api.depends('date_from', 'date_to', 'struct_id')
    def _compute_is_wrong_duration(self):
        for slip in self:
            slip.is_wrong_duration = slip.date_to and (
                slip.version_id.schedule_pay
                or slip.version_id.structure_type_id.default_schedule_pay
            ) and (
                slip.date_from + slip._get_schedule_timedelta() != slip.date_to
            )

    @api.depends('employee_id', 'version_id', 'struct_id', 'date_from', 'date_to')
    def _compute_worked_days_line_ids(self):
        if not self or self.env.context.get('salary_simulation'):
            return
        valid_slips = self.filtered(lambda p: p.employee_id and p.date_from and p.date_to and p.version_id and p.struct_id and p.struct_id.use_worked_day_lines)
        if not valid_slips:
            return
        # Make sure to reset invalid payslip's worked days line
        self.update({'worked_days_line_ids': [(5, 0, 0)]})
        # Ensure work entries are generated for all contracts
        generate_from = min(p.date_from for p in valid_slips) + relativedelta(days=-1)
        generate_to = max(p.date_to for p in valid_slips) + relativedelta(days=1)
        self.version_id.filtered('resource_calendar_id').generate_work_entries(generate_from, generate_to)
        work_entries = self.env['hr.work.entry'].search([
            ('date', '<=', generate_to),
            ('date', '>=', generate_from),
            ('version_id', 'in', self.version_id.ids),
        ])
        work_entries_by_version = defaultdict(lambda: self.env['hr.work.entry'])
        for work_entry in work_entries:
            work_entries_by_version[work_entry.version_id.id] += work_entry

        for slip in valid_slips:
            if not slip.struct_id.use_worked_day_lines:
                continue

            # convert slip.date_to to a datetime with max time to compare correctly in filtered_domain.
            slip_tz = pytz.timezone(slip.version_id.resource_calendar_id.tz or slip.employee_id.tz or slip.company_id.resource_calendar_id.tz or 'UTC')
            utc = pytz.timezone('UTC')
            date_from = slip_tz.localize(datetime.combine(slip.date_from, time.min)).astimezone(utc).replace(tzinfo=None)
            date_to = slip_tz.localize(datetime.combine(slip.date_to, time.max)).astimezone(utc).replace(tzinfo=None)
            payslip_work_entries = work_entries_by_version[slip.version_id].filtered_domain([
                ('date', '<=', date_to),
                ('date', '>=', date_from),
            ])
            payslip_work_entries._check_undefined_slots(slip.date_from, slip.date_to)
            # YTI Note: We can't use a batched create here as the payslip may not exist
            slip.update({'worked_days_line_ids': slip._get_new_worked_days_lines()})

    def _get_similar_payslips(self):
        done_payslips = self.filtered(lambda p: p.employee_id and p.struct_id and p.date_from and p.date_to)
        search_domain = [
            ('employee_id', 'in', done_payslips.employee_id.ids),
            ('struct_id', 'in', done_payslips.struct_id.ids),
            ('date_from', 'in', done_payslips.mapped('date_from')),
            ('date_to', 'in', done_payslips.mapped('date_to')),
            ('state', 'in', ['validated', 'paid'])
        ]
        all_existing_payslips = self.env['hr.payslip'].search(search_domain)

        # Group existing slips for easy lookup
        existing_payslip_map = defaultdict(lambda: self.env['hr.payslip'])
        for slip in all_existing_payslips:
            key = (slip.employee_id.id, slip.struct_id.id, slip.date_from, slip.date_to)
            existing_payslip_map[key] |= slip

        return existing_payslip_map

    def _get_new_worked_days_lines(self):
        if self.struct_id.use_worked_day_lines:
            return [(0, 0, vals) for vals in self._get_worked_day_lines()]
        return []

    def _get_salary_line_total(self, code):
        _logger.warning('The method _get_salary_line_total is deprecated in favor of _get_line_values')
        lines = self.line_ids.filtered(lambda line: line.code == code)
        return sum([line.total for line in lines])

    def _get_salary_line_quantity(self, code):
        _logger.warning('The method _get_salary_line_quantity is deprecated in favor of _get_line_values')
        lines = self.line_ids.filtered(lambda line: line.code == code)
        return sum([line.quantity for line in lines])

    def _get_line_values(self, code_list, vals_list=None, compute_sum=False):
        if vals_list is None:
            vals_list = ['total']
        valid_values = {'quantity', 'amount', 'total', 'ytd'}
        if set(vals_list) - valid_values:
            raise UserError(_('The following values are not valid:\n%s', '\n'.join(list(set(vals_list) - valid_values))))
        result = defaultdict(lambda: defaultdict(lambda: dict.fromkeys(vals_list, 0.0)))
        if not self or not code_list:
            return result
        payslip_line_read_group = self.env['hr.payslip.line']._read_group(
            [
                ('slip_id', 'in', self.ids),
                ('code', 'in', code_list),
            ],
            ['slip_id', 'code'],
            [f'{f_name}:sum' for f_name in vals_list],
        )
        # result = {
        #     'IP': {
        #         'sum': {'quantity': 2, 'total': 300},
        #         1: {'quantity': 1, 'total': 100},
        #         2: {'quantity': 1, 'total': 200},
        #     },
        #     'IP.DED': {
        #         'sum': {'quantity': 2, 'total': -5},
        #         1: {'quantity': 1, 'total': -2},
        #         2: {'quantity': 1, 'total': -3},
        #     },
        # }
        for payslip, code, *sum_vals_list in payslip_line_read_group:
            for vals, vals_value in zip(vals_list, sum_vals_list):
                if compute_sum:
                    result[code]['sum'][vals] += vals_value or 0.0
                result[code][payslip.id][vals] += vals_value or 0.0
        return result

    def _get_worked_days_line_values_orm(self, code, field_name=None):
        """
        Use this method only if self is not yet created.
        Otherwise, use '_get_worked_days_line_values' that leads to better performances.
        """
        if field_name is None:
            field_name = 'amount'
        valid_values = {'number_of_hours', 'number_of_days', 'amount', 'ytd'}
        if field_name not in valid_values:
            raise UserError(_('The field is not valid:%s', field_name))

        wds = self.worked_days_line_ids.filtered(lambda wd: wd.code == code)
        return sum(wd[field_name] for wd in wds)

    def _get_worked_days_line_values(self, code_list, vals_list=None, compute_sum=False, exclude_codes=False):
        if vals_list is None:
            vals_list = ['amount']
        valid_values = {'number_of_hours', 'number_of_days', 'amount', 'ytd'}
        if set(vals_list) - valid_values:
            raise UserError(_('The following values are not valid:\n%s', '\n'.join(list(set(vals_list) - valid_values))))
        result = defaultdict(lambda: defaultdict(lambda: dict.fromkeys(vals_list, 0.0)))
        if not self or (not code_list and not exclude_codes):
            return result

        self.env.flush_all()
        selected_fields = ','.join('SUM(%s) AS %s' % (vals, vals) for vals in vals_list)
        operation = 'IN' if not exclude_codes else 'NOT IN'
        self.env.cr.execute("""
            SELECT
                p.id,
                wet.code,
                %s
            FROM hr_payslip_worked_days wd
            JOIN hr_work_entry_type wet ON wet.id = wd.work_entry_type_id
            JOIN hr_payslip p ON p.id IN %s
            AND wd.payslip_id = p.id
            AND wet.code %s %s
            GROUP BY p.id, wet.code
        """ % (selected_fields, '%s', operation, '%s'), (tuple(self.ids), tuple(code_list)))
        # self = hr.payslip(1, 2)
        # request_rows = [
        #     {'id': 1, 'code': 'WORK100', 'amount': 100, 'number_of_days': 1},
        #     {'id': 1, 'code': 'LEAVE100', 'amount': 200, 'number_of_days': 1},
        #     {'id': 2, 'code': 'WORK100', 'amount': -2, 'number_of_days': 1},
        #     {'id': 2, 'code': 'LEAVE100', 'amount': -3, 'number_of_days': 1}
        # ]
        request_rows = self.env.cr.dictfetchall()
        # result = {
        #     'IP': {
        #         'sum': {'number_of_days': 2, 'amount': 300},
        #         1: {'number_of_days': 1, 'amount': 100},
        #         2: {'number_of_days': 1, 'amount': 200},
        #     },
        #     'LEAVE100': {
        #         'sum': {'number_of_days': 2, 'amount': -5},
        #         1: {'number_of_days': 1, 'amount': -2},
        #         2: {'number_of_days': 1, 'amount': -3},
        #     },
        # }
        for row in request_rows:
            code = row['code']
            payslip_id = row['id']
            for vals in vals_list:
                if compute_sum:
                    result[code]['sum'][vals] += row[vals] or 0.0
                result[code][payslip_id][vals] += row[vals] or 0.0
        return result

    # YTI TODO: Convert in a single SQL request + Handle children
    def _get_category_data(self, category_code):
        category_data = {'quantity': 0.0, 'total': 0.0}
        for line in self.line_ids:
            if line.category_id.code == category_code:
                category_data['quantity'] += line.quantity
                category_data['total'] += line.total
        return category_data

    def _get_input_line_amount(self, code):
        lines = self.input_line_ids.filtered(lambda line: line.code == code)
        return sum([line.amount for line in lines])

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options)
        if options and options.get('toolbar'):
            for view_type in res['views']:
                res['views'][view_type]['toolbar'].pop('print', None)
        return res

    def action_print_payslip(self):
        if self.filtered('error_count'):
            raise ValidationError(self._get_error_message())
        return {
            'name': 'Payslip',
            'type': 'ir.actions.act_url',
            'url': '/print/payslips?list_ids=%(list_ids)s' % {'list_ids': ','.join(str(x) for x in self.ids)},
        }

    def action_export_payslip(self):
        pass

    def _get_contract_wage(self):
        self.ensure_one()
        return self.version_id._get_contract_wage()

    def _get_paid_amount(self):
        self.ensure_one()
        if self.env.context.get('no_paid_amount'):
            return 0.0
        if self.env.context.get('salary_simulation') or not self.struct_id.use_worked_day_lines:
            return self._get_contract_wage()
        total_amount = 0
        for line in self.worked_days_line_ids:
            total_amount += line.amount
        return total_amount

    def _get_unpaid_amount(self):
        self.ensure_one()
        return self._get_contract_wage() - self._get_paid_amount()

    def _is_outside_contract_dates(self):
        self.ensure_one()
        payslip = self
        contract = self.version_id
        return contract.date_start > payslip.date_to or (contract.date_end and contract.date_end < payslip.date_from)

    def _get_data_files_to_update(self):
        # Note: Use lists as modules/files order should be maintained
        return []

    def _update_payroll_data(self):
        data_to_update = self._get_data_files_to_update()
        _logger.info("Update payroll static data")
        idref = {}
        for module_name, files_to_update in data_to_update:
            for file_to_update in files_to_update:
                convert_file(self.env, module_name, file_to_update, idref)

    def action_edit_payslip_lines(self):
        self.ensure_one()
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(_('This action is restricted to payroll officers only.'))
        if self.state == 'validated':
            raise UserError(_('This action is forbidden on validated payslips.'))
        wizard = self.env['hr.payroll.edit.payslip.lines.wizard'].create({
            'payslip_id': self.id,
            'line_ids': [(0, 0, {
                'sequence': line.sequence,
                'code': line.code,
                'name': line.name,
                'salary_rule_id': line.salary_rule_id.id,
                'version_id': line.version_id.id,
                'employee_id': line.employee_id.id,
                'amount': line.amount,
                'quantity': line.quantity,
                'rate': line.rate,
                'ytd': line.ytd,
                'slip_id': self.id}) for line in self.line_ids],
            'worked_days_line_ids': [(0, 0, {
                'name': line.name,
                'sequence': line.sequence,
                'code': line.code,
                'work_entry_type_id': line.work_entry_type_id.id,
                'number_of_days': line.number_of_days,
                'number_of_hours': line.number_of_hours,
                'amount': line.amount,
                'ytd': line.ytd,
                'slip_id': self.id}) for line in self.worked_days_line_ids]
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Edit Payslip Lines'),
            'res_model': 'hr.payroll.edit.payslip.lines.wizard',
            'view_mode': 'form',
            'target': 'new',
            'binding_model_id': self.env['ir.model.data']._xmlid_to_res_id('hr_payroll.model_hr_payslip'),
            'binding_view_types': 'form',
            'res_id': wizard.id
        }

    @api.model
    def _cron_generate_pdf(self, batch_size=False):
        payslips = self.search([
            ('state', 'in', ['validated', 'paid']),
            ('queued_for_pdf', '=', True),
        ])
        if payslips:
            BATCH_SIZE = batch_size or 30
            payslips_batch = payslips[:BATCH_SIZE]
            payslips_batch._generate_pdf()
            payslips_batch.write({'queued_for_pdf': False})
            # if necessary, retrigger the cron to generate more pdfs
            if len(payslips) > BATCH_SIZE:
                self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
                return True

        lines = self.env['hr.payroll.employee.declaration'].search([('pdf_to_generate', '=', True)])
        if lines:
            BATCH_SIZE = batch_size or 30
            lines_batch = lines[:BATCH_SIZE]
            lines_batch._generate_pdf()
            lines_batch.write({'pdf_to_generate': False})
            # if necessary, retrigger the cron to generate more pdfs
            if len(lines) > BATCH_SIZE:
                self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
                return True
        return False

    @api.model
    def __get_aggregator_hr_payslip_input_model(self):
        """this method return an aggregator version of hr.payslip.input Model.
        this method is also meant to be overriden in case other modules adds new fields
        to hr.payslip.input model. In case it can be extended as such:
        ```py
        def __get_aggregator_hr_payslip_input_model(self):
            class ProxyHrPayslipInput(super().__get_aggregator_hr_payslip_input_model()):
                ... # your modifications
        return ProxyHrPayslipInput
        ```

        Note: -this method use the normal python class inheritance instead of odoo's
              -the aggregation assumes that the code are the same for all the inputs
        Warning: Do not reproduce elsewhere it's quite a specific case here
        return: Aggregator version of hr.payslip.input model
        """

        class ProxyHrPayslipInput(self.env['hr.payslip.input'].__class__):
            _name = self.env['hr.payslip.input']._name
            _register = False  # invisible to the ORM

            # All the fields that are not overridden are considered as equal to
            # self[0]['field']

            def __getitem__(self, key_or_slice):
                if not self or len(self) == 1:
                    return super().__getitem__(key_or_slice)
                if key_or_slice == 'name':
                    return self.name
                if key_or_slice == 'sequence':
                    return self.sequence
                if key_or_slice == 'amount':
                    return self.amount
                return super().__getitem__(key_or_slice)

            @property
            def name(self):
                if not self or len(self) == 1:
                    return super().name
                if len(set(self.mapped('name'))) == 1:
                    return super(ProxyHrPayslipInput, self[0]).name
                return ', '.join(self.mapped('name'))

            @property
            def sequence(self):
                if not self or len(self) == 1:
                    return super().sequence
                return min(self.mapped('sequence'))

            @property
            def amount(self):
                if not self or len(self) == 1:
                    return super().amount
                return sum([payslip_input.amount for payslip_input in self])

        return ProxyHrPayslipInput

    # Payroll Dashboard
    @api.model
    def _dashboard_default_action(self, name, res_model, res_ids, additional_context=None):
        if additional_context is None:
            additional_context = {}
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'context': {**self.env.context, **additional_context},
            'domain': [('id', 'in', res_ids)],
            'views': [[False, 'list'], [False, 'kanban'], [False, 'form']],
            'view_mode': 'list,kanban,form',
        }

    @api.model
    def get_dashboard_warnings(self):
        # Retrieve the different warnings to display on the actions section (box on the left)
        result = []

        # Retrieves last batches (this month, or last month)
        batch_limit_date = fields.Date.today() - relativedelta(months=1, day=1)
        batch_group_read = self.env['hr.payslip.run'].with_context(lang='en_US')._read_group(
            [('date_start', '>=', fields.Date.today() - relativedelta(months=1, day=1))],
            groupby=['date_start:month'],
            order='date_start:month desc')
        # Keep only the last month
        batch_group_read = batch_group_read[:1]
        if batch_group_read:
            min_date = batch_group_read[-1][0] or batch_limit_date
            last_batches = self.env['hr.payslip.run'].search([('date_start', '>=', min_date)])
        else:
            last_batches = self.env['hr.payslip.run']

        for warning in self.env['hr.payroll.dashboard.warning'].search([]):
            context = {
                'date': safe_eval_datetime.date,
                'datetime': safe_eval_datetime.datetime,
                'relativedelta': safe_eval_dateutil.relativedelta.relativedelta,
                'warning_count': 0,
                'warning_records': self.env['base'],
                'warning_action': False,
                'additional_context': {},
                'self': self.env['hr.payslip'],
                'last_batches': last_batches,
                'defaultdict': defaultdict,
            }
            try:
                safe_eval(warning.evaluation_code, context, mode='exec')
            except Exception as e:
                raise UserError(_("Wrong warning computation code defined for:\n- Warning: %(warning)s\n- Error: %(error)s", warning=warning.name, error=e))
            if context['warning_count']:
                result.append({
                    'string': warning.name,
                    'color': warning.color,
                    'count': context['warning_count'],
                    'action': context['warning_action'] or self._dashboard_default_action(
                        warning.name,
                        context['warning_records']._name,
                        context['warning_records'].ids,
                        additional_context=context['additional_context'],
                    ),
                })
        return result

    def _get_employee_stats_actions(self):
        result = []
        today = fields.Date.today()
        HrVersion = self.env['hr.version']
        new_versions = HrVersion.search([('contract_date_start', '>=', today + relativedelta(months=-3, day=1))])
        past_versions_grouped_by_employee_id = {
            employee.id
            for [employee] in HrVersion._read_group([
                ('employee_id', 'in', new_versions.employee_id.ids),
                # ('date_end', '<', today),  # TODO: filter after
                ('id', 'not in', new_versions.ids)
            ], groupby=['employee_id'])
        }

        new_versions_without_past_version = HrVersion
        for new_version in new_versions:
            if new_version.employee_id.id not in past_versions_grouped_by_employee_id:
                new_versions_without_past_version |= new_version

        if new_versions_without_past_version:
            new_versions_str = _('New Employees')
            employees_from_new_versions = new_versions_without_past_version.mapped('employee_id')
            new_employees = {
                'string': new_versions_str,
                'count': len(employees_from_new_versions),
                'action': self._dashboard_default_action(new_versions_str, 'hr.employee', employees_from_new_versions.ids),
            }
            new_employees['action']['views'][0] = [self.env.ref('hr_payroll.payroll_hr_employee_view_tree_employee_trends').id, 'list']
            result.append(new_employees)

        gone_employees = self.env['hr.employee'].with_context(active_test=False).search([
            ('departure_date', '>=', today + relativedelta(months=-1, day=1)),
            ('company_id', 'in', self.env.companies.ids),
        ])
        if gone_employees:
            gone_employees_str = _('Last Departures')
            result.append({
                'string': gone_employees_str,
                'count': len(gone_employees),
                'action': self.with_context(active_test=False)._dashboard_default_action(
                    gone_employees_str, 'hr.employee', gone_employees.ids),
            })
        return result

    @api.model
    def _get_dashboard_stat_employer_cost_codes(self):
        costs = self.env['hr.salary.rule'].search_read([
            ('appears_on_employee_cost_dashboard', '=', True)],
            fields=['code', 'name'])
        cost_codes = {}

        for cost in costs:
            cost_codes[cost['code']] = cost['name']
        return cost_codes

    @api.model
    def _get_dashboard_stats_employer_cost(self):
        today = fields.Date.context_today(self)
        date_formats = {
            'monthly': 'MMMM y',
            'yearly': 'y',
        }
        employer_cost = {
            'type': 'stacked_bar',
            'title': _('Employer Cost'),
            'label': _('Employer Cost'),
            'id': 'employer_cost',
            'is_sample': False,
            'actions': [],
            'data': {
                'monthly': defaultdict(lambda: [{}, {}, {}]),
                'yearly': defaultdict(lambda: [{}, {}, {}]),
            },
        }
        # Retrieve employer costs over the last 3 months
        last_payslips = self.env['hr.payslip'].search([
            ('state', '!=', 'cancel'),
            ('date_from', '>=', fields.Date.today() + relativedelta(months=-2, day=1)),
            ('date_to', '<=', fields.Date.today() + relativedelta(day=31))
        ])
        if not last_payslips:
            employer_cost['is_sample'] = True
        cost_codes = self._get_dashboard_stat_employer_cost_codes()
        line_values = last_payslips._get_line_values(cost_codes.keys())
        for slip in last_payslips:
            for code, code_desc in cost_codes.items():
                start = slip.date_from
                end = today
                idx = -((end.year - start.year) * 12 + (end.month - start.month) - 2)
                amount = employer_cost['data']['monthly'][code_desc][idx].get('value', 0.0)
                amount += line_values[code][slip.id]['total']
                employer_cost['data']['monthly'][code_desc][idx]['value'] = amount
                if not employer_cost['data']['monthly'][code_desc][idx].get('label'):
                    period_str = format_date(self.env, start, date_format=date_formats['monthly'])
                    employer_cost['data']['monthly'][code_desc][idx]['label'] = period_str
        # Retrieve employer costs over the last 3 years
        last_payslips = self.env['hr.payslip'].search([
            ('state', '!=', 'cancel'),
            ('date_from', '>=', fields.Date.today() + relativedelta(years=-2, day=1)),
            ('date_to', '<=', fields.Date.today() + relativedelta(month=12, day=31))
        ])
        line_values = last_payslips._get_line_values(cost_codes.keys())
        for slip in last_payslips:
            for code, code_desc in cost_codes.items():
                start = slip.date_from
                end = today
                idx = -(end.year - start.year - 2)
                amount = employer_cost['data']['yearly'][code_desc][idx].get('value', 0.0)
                amount += line_values[code][slip.id]['total']
                employer_cost['data']['yearly'][code_desc][idx]['value'] = amount
                if not employer_cost['data']['yearly'][code_desc][idx].get('label'):
                    period_str = format_date(self.env, start, date_format=date_formats['yearly'])
                    employer_cost['data']['yearly'][code_desc][idx]['label'] = period_str
        # Nullify empty sections
        for i in range(3):
            for code_desc in cost_codes.values():
                if not employer_cost['data']['monthly'][code_desc][i]:
                    value = 0 if not employer_cost['is_sample'] else random.randint(1000, 1500)
                    employer_cost['data']['monthly'][code_desc][i]['value'] = value
                    if not employer_cost['data']['monthly'][code_desc][i].get('label'):
                        label = format_date(self.env, today + relativedelta(months=i-2), date_format=date_formats['monthly'])
                        employer_cost['data']['monthly'][code_desc][i]['label'] = label
                if not employer_cost['data']['yearly'][code_desc][i]:
                    value = 0 if not employer_cost['is_sample'] else random.randint(10000, 15000)
                    employer_cost['data']['yearly'][code_desc][i]['value'] = value
                    if not employer_cost['data']['yearly'][code_desc][i].get('label'):
                        label = format_date(self.env, today + relativedelta(years=i-2), date_format=date_formats['yearly'])
                        employer_cost['data']['yearly'][code_desc][i]['label'] = label
        # Format/Round at the end as the method cost is heavy
        for data_by_code in employer_cost['data'].values():
            for data_by_type in data_by_code.values():
                for data_dict in data_by_type:
                    value = round(data_dict['value'], 2)
                    data_dict['value'] = value
                    data_dict['formatted_value'] = format_amount(self.env, value, self.env.company.currency_id)
        return employer_cost

    @api.model
    def _get_dashboard_stat_employee_trends(self):
        today = fields.Date.context_today(self)
        employees_trends = {
            'type': 'bar',
            'title': _('Employee Count'),
            'label': _('Employee Count'),
            'id': 'employees',
            'is_sample': False,
            'actions': self._get_employee_stats_actions(),
            'data': {
                'monthly': [{}, {}, {}],
                'yearly': [{}, {}, {}],
            },
        }
        # These are all the periods for which we need data
        periods = [
            # Last month
            (today - relativedelta(months=1, day=1), today - relativedelta(day=1, days=1), 'monthly,past'),
            # This month
            (today - relativedelta(day=1), today + relativedelta(months=1, day=1, days=-1), 'monthly,present'),
            # Next month
            (today + relativedelta(months=1, day=1), today + relativedelta(months=2, day=1, days=-1), 'monthly,future'),
            # Last year
            (today - relativedelta(years=1, month=1, day=1), today - relativedelta(years=1, month=12, day=31), 'yearly,past'),
            # This year
            (today - relativedelta(month=1, day=1), today + relativedelta(month=12, day=31), 'yearly,present'),
            # Next year
            (today + relativedelta(years=1, month=1, day=1), today + relativedelta(years=1, month=12, day=31), 'yearly,future'),
        ]
        periods_str = ', '.join(
            "(DATE '%(date_from)s', DATE '%(date_to)s', '%(date_type)s')" % {
                'date_from': p[0].strftime('%Y-%m-%d'),
                'date_to': p[1].strftime('%Y-%m-%d'),
                'date_type': p[2],
            } for p in periods)
        # Fetch our statistics
        # Contracts are joined by our period using the usual state/date conditions
        # and aggregates are used to collect data directly from our database
        # avoiding unnecessary orm overhead
        # TODO: should filter with date_start, date_end via orm or is it already good ? will this stay at all ?
        self.env.cr.execute("""
        WITH periods AS (
            SELECT *
              FROM (VALUES %s
              ) x(start, _end, _type)
        )
        -- fetch all contracts matching periods from `periods`
        SELECT p.start, p._end, p._type, ARRAY_AGG(v.id),
               COUNT (DISTINCT v.employee_id) as employee_count
          FROM periods p
          JOIN hr_version v
            ON (v.contract_date_end >= p.start OR v.contract_date_end IS NULL)
           AND v.contract_date_start <= p._end
          JOIN hr_employee e
            ON e.id = v.employee_id
           AND e.company_id IN %%s
      GROUP BY p.start, p._end, p._type
        """ % (periods_str), (tuple(self.env.companies.ids),))
        period_indexes = {
            'past': 0,
            'present': 1,
            'future': 2,
        }
        date_formats = {
            'monthly': 'MMMM y',
            'yearly': 'y',
        }
        # Collect data in our result
        for res in self.env.cr.dictfetchall():
            period_type, _type = res['_type'].split(',')  # Ex: yearly,past
            start = res['start']
            period_idx = period_indexes[_type]
            period_str = format_date(self.env, start, date_format=date_formats[period_type])
            # The data is formatted for the chart module
            employees_trends['data'][period_type][period_idx] = {
                'label': period_str,
                'value': res['employee_count'],
                'name': period_str,
            }

        # Generates a point as sample data
        def make_sample_data(period_str, period_type, chart_type):
            if chart_type == 'line':
                return {'x': period_str, 'name': period_str, 'y': random.randint(1000, 1500)}
            return {'value': random.randint(1000, 1500), 'label': period_str, 'type': period_type}

        # Generates empty data in case a column is missing
        def make_null_data(period_str, period_type, chart_type):
            if chart_type == 'line':
                return {'x': period_str, 'name': period_str, 'y': 0}
            return {'value': 0, 'label': period_str, 'type': period_type}

        make_data = make_null_data
        period_types = ['monthly', 'yearly']

        if all(not data for data in employees_trends['data']['monthly']):
            employees_trends['is_sample'] = True
            make_data = make_sample_data

        # Go through all the data and create null or sample values where necessary
        for start, _dummy, p_types in periods:
            _type, _time = p_types.split(',')
            i = period_indexes[_time]
            for period in period_types:
                period_str = format_date(self.env, start, date_format=date_formats[period])
                if not employees_trends['data'][_type][i]:
                    employees_trends['data'][_type][i] = make_data(
                        period_str, _type, employees_trends['type'])
        return employees_trends

    @api.model
    def _get_dashboard_stats(self):
        # Retrieve the different stats to display on the stats sections
        # This function fills in employees and employer costs statistics
        # Default data, replaced by sample data if empty after query
        employees_trends = self._get_dashboard_stat_employee_trends()
        employer_cost = self._get_dashboard_stats_employer_cost()

        return [employer_cost, employees_trends]

    @api.model
    def _get_dashboard_employee_count(self):
        admin_employee = self.env.ref('hr.employee_admin', raise_if_not_found=False)
        domain = [('company_id', 'in', self.env.companies.ids)]
        if admin_employee:
            domain += [('id', '!=', admin_employee.id)]
        return self.env['hr.employee'].search_count(domain, limit=1)

    @api.model
    def _get_dashboard_default_sections(self):
        return ['batches', 'stats', 'employee_count']

    @api.model
    def _get_dashboard_batch_fields(self):
        return ['id', 'date_start', 'name', 'state', 'payslip_count']

    @api.model
    def get_payroll_dashboard_data(self, sections=None):
        # Entry point for getting the dashboard data
        # `sections` defines which part of the data we want to include/exclude
        if sections is None:
            sections = self._get_dashboard_default_sections()
        result = {}
        if 'batches' in sections:
            # Batches are loaded for the last 3 months with batches, for example if there are no batches for
            # the summer and september is loaded, we want to get september, june, may.
            # Limit to max - 1 year
            batch_limit_date = fields.Date.today() - relativedelta(years=1, day=1)
            batch_group_read = self.env['hr.payslip.run'].with_context(lang='en_US')._read_group(
                [('date_start', '>=', batch_limit_date)],
                groupby=['date_start:month'],
                limit=20,
                order='date_start:month desc')
            # Keep only the last 3 months
            batch_group_read = batch_group_read[:3]
            if batch_group_read:
                min_date = batch_group_read[-1][0] or fields.Date.today() - relativedelta(months=1, day=1)
                batches_read_result = self.env['hr.payslip.run'].search_read(
                    [('date_start', '>=', min_date)],
                    fields=self._get_dashboard_batch_fields())
            else:
                batches_read_result = []
            translated_states = dict(self.env['hr.payslip.run']._fields['state']._description_selection(self.env))
            for batch_read in batches_read_result:
                batch_read.update({
                    'name': f"{batch_read['name']} ({format_date(self.env, batch_read['date_start'], date_format='MM/y')})",
                    'payslip_count': _('(%s Payslips)', batch_read['payslip_count']),
                    'state': translated_states.get(batch_read['state'], _('Unknown State')),
                })
            result['batches'] = batches_read_result
        if 'stats' in sections:
            result['stats'] = self._get_dashboard_stats()
        if 'employee_count' in sections:
            result['employee_count'] = self._get_dashboard_employee_count()
        return result

    def action_configure_payslip_inputs(self):
        self.ensure_one()
        return self.struct_id.action_get_structure_inputs()

    def compute_salary_allocations(self, total_amount=None):
        self.ensure_one()
        if total_amount is None:
            remaining = self.currency_id.round(self.net_wage)
        else:
            remaining = self.currency_id.round(total_amount)

        res = {}
        if remaining == 0 or not self.employee_id.bank_account_ids:
            return res
        if not self.employee_id.has_multiple_bank_accounts:
            res[str(self.employee_id.primary_bank_account_id.id)] = remaining
            return res

        fixed_bank_account_ids = self.employee_id.get_accounts_with_fixed_allocations()
        for ba in fixed_bank_account_ids:
            amount, _ = self.employee_id.get_bank_account_salary_allocation(str(ba.id))
            if amount > 0 and amount <= remaining:
                amount = self.currency_id.round(amount)
                res[str(ba.id)] = amount
                remaining -= amount
                if remaining < 0:
                    raise ValidationError(self.env._("Allocated amounts surpass the net salary."))
            else:
                raise ValidationError(self.env._("Allocated amounts surpass the net salary."))

        percentage_bank_account_ids = self.employee_id.bank_account_ids - fixed_bank_account_ids
        if not percentage_bank_account_ids and remaining > 0:
            raise ValidationError(self.env._("Allocated amounts are less than the net salary."))

        total_percentage_account_amounts = 0
        for i, ba in enumerate(percentage_bank_account_ids):
            percentage, _ = self.employee_id.get_bank_account_salary_allocation(str(ba.id))
            if percentage > 0:
                if i == len(percentage_bank_account_ids) - 1:
                    amount = self.currency_id.round(remaining - total_percentage_account_amounts)
                else:
                    amount = self.currency_id.round((percentage / 100.0) * remaining)
                    total_percentage_account_amounts += amount
                if amount > 0:
                    res[str(ba.id)] = amount
            else:
                res[str(ba.id)] = 0
        return res

    def safe_compute_salary_allocations(self, total_amount=None):
        try:
            return self.compute_salary_allocations(total_amount)
        except ValidationError as e:
            return {"__error__": str(e)}
