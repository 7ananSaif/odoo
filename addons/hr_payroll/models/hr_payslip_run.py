# Part of Odoo. See LICENSE file for full copyright and licensing details.
from ast import literal_eval
from collections import defaultdict
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta
import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.tools.date_utils import get_month

STATUS_COLOR = {
    '01_ready': 4,  # info light blue
    '02_close': 10,  # success green
    '03_paid': 5,  # primary purple
    '04_cancel': 0,  # default grey
    False: 0,  # default grey -- for studio
}


class HrPayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Pay Run'
    _order = 'date_end desc'

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    slip_ids = fields.One2many('hr.payslip', 'payslip_run_id', string='Payslips')
    state = fields.Selection([
            ('01_ready', 'Ready'),
            ('02_close', 'Done'),
            ('03_paid', 'Paid'),
            ('04_cancel', 'Cancelled'),
        ],
        string='Status', index=True, readonly=True, copy=False,
        default='01_ready', tracking=True,
        compute='_compute_state', store=True)
    color = fields.Integer(compute='_compute_color', export_string_translation=False)
    date_start = fields.Date(
        string='From', readonly=False, required=True,
        compute="_compute_date_start", store=True, precompute=True,
        default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_end = fields.Date(
        string='To', readonly=False, required=True,
        compute="_compute_date_end", store=True, precompute=True,
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    structure_id = fields.Many2one('hr.payroll.structure', string='Salary Structure', readonly=False)
    use_worked_day_lines = fields.Boolean(related='structure_id.use_worked_day_lines')
    schedule_pay = fields.Selection(
        selection=lambda self: self.env['hr.payroll.structure.type']._get_selection_schedule_pay(),
        compute='_compute_schedule_pay', default="monthly", readonly=False, store=True, precompute=True, string='Pay Schedule')
    payslip_count = fields.Integer(compute='_compute_payslip_count', store=True)
    payslips_with_issues = fields.Integer(compute='_compute_payslips_with_issues')
    has_error = fields.Boolean(compute='_compute_has_error')
    empty_payslips = fields.Integer(compute='_compute_empty_payslips')
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    country_id = fields.Many2one(
        'res.country', string='Country',
        related='company_id.country_id', readonly=True
    )
    country_code = fields.Char(related='country_id.code', depends=['country_id'], readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    payment_report = fields.Binary(
        string='Payment Report',
        help="Export .csv file related to this pay run",
        readonly=True)
    payment_report_filename = fields.Char(readonly=True)
    payment_report_format = fields.Char(readonly=True)
    payment_report_date = fields.Date(readonly=True)
    total_employer_cost = fields.Monetary(compute='_compute_total_employer_cost', string='Total Employer Cost')
    gross_sum = fields.Monetary(compute="_compute_gross_net_sum", store=True, readonly=True, copy=False)
    net_sum = fields.Monetary(compute="_compute_gross_net_sum", store=True, readonly=True, copy=False)

    def _get_name_for_period(self, vals=None, cache=None):

        def normalize_date(val):
            if isinstance(val, date):
                return val
            elif isinstance(val, datetime):
                return val.date()
            elif isinstance(val, str):
                return date.fromisoformat(val)
            return None

        if vals is None:
            vals = {}
        if cache is None:
            cache = {}
        if not vals.get("date_start") or not vals.get("date_end"):
            raise UserError(self.env._("You must set a start and end date for the Pay Run"))
        date_start = normalize_date(vals["date_start"])
        date_end = normalize_date(vals["date_end"])
        structure_id = vals.get("structure_id")
        name = ""
        if not date_start or not date_end:
            return name
        format_date_cached = self.env["hr.payslip"]._format_date_cached
        if date_end.year == date_start.year:
            if date_end.month - date_start.month == 11:
                name += format_date_cached(cache, date_start, date_format="Y")
            elif date_end.month == date_start.month:
                if (date_start, date_end) == get_month(date_start):
                    name += format_date_cached(cache, date_start, date_format="MMM Y")
                elif date_start.day == date_end.day:
                    name += format_date_cached(cache, date_start, date_format="d MMM Y")
                else:
                    name += format_date_cached(cache, date_start, date_format="d MMM Y") + " - " + format_date_cached(cache, date_end, date_format="d MMM Y")
            else:
                name += format_date_cached(cache, date_start, date_format="MMM Y") + " - " + format_date_cached(cache, date_end, date_format="MMM Y")
        else:
            name += format_date_cached(cache, date_start, date_format="Y") + " - " + format_date_cached(cache, date_end, date_format="Y")
        if structure_id:
            structure_id = self.env["hr.payroll.structure"].browse(structure_id)
            name += " - " + structure_id.name
        return name

    def _get_valid_version_ids(self, date_start=None, date_end=None, structure_id=None, company_id=None, employee_ids=None, schedule_pay=None):
        date_start = date_start or self.date_start
        date_end = date_end or self.date_end
        structure = self.env["hr.payroll.structure"].browse(structure_id) if structure_id else self.structure_id
        schedule_pay = schedule_pay or self.schedule_pay
        company = company_id or self.company_id.id
        version_domain = Domain([
            ('company_id', '=', company),
            ('employee_id', '!=', False),
            ('contract_date_start', '<=', date_end),
            '|',
                ('contract_date_end', '=', False),
                ('contract_date_end', '>=', date_start),
            ('date_version', '<=', date_end),
            ('structure_type_id', '!=', False),
        ])
        if structure:
            version_domain &= Domain([('structure_type_id', '=', structure.type_id.id)])
        if employee_ids:
            version_domain &= Domain([('employee_id', 'in', employee_ids)])
        if schedule_pay:
            version_domain &= Domain([('schedule_pay', '=', schedule_pay)])
        all_versions = self.env['hr.version']._read_group(
            domain=version_domain,
            groupby=['employee_id', 'date_version:day'],
            order="date_version:day DESC",
            aggregates=['id:recordset'],
        )
        all_employee_versions = defaultdict(list)
        for employee, _, version in all_versions:
            all_employee_versions[employee] += [*version]
        valid_versions = self.env["hr.version"]
        for employee_versions in all_employee_versions.values():
            employee_valid_versions = self.env["hr.version"]
            for i in range(len(employee_versions)):
                version = employee_versions[i]
                if version.date_version <= date_start or employee_versions[-1] == version:
                    # End case: The first version in contract before the pay run start or the last version of the list
                    employee_valid_versions |= version
                    break
                if employee_valid_versions:
                    # Version already added => new contract?
                    if (employee_valid_versions[-1].contract_date_start > version.contract_date_start
                        and (version.contract_date_start >= version.date_version
                            or version.contract_date_start > employee_versions[i + 1].contract_date_start)):
                        # Take only the first version of the new contract founded
                        employee_valid_versions |= version
                elif version.contract_date_start >= version.date_version or version.contract_date_start > employee_versions[i + 1].contract_date_start:
                    # Take only the first version of the first contract founded
                    employee_valid_versions |= version
            valid_versions |= employee_valid_versions
        return valid_versions.ids

    @api.depends("structure_id")
    def _compute_schedule_pay(self):
        for payslip_run in self:
            payslip_run.schedule_pay = payslip_run.structure_id.type_id.default_schedule_pay

    @api.depends("slip_ids")
    def _compute_payslip_count(self):
        for payslip_run in self:
            payslip_run.payslip_count = len(payslip_run.slip_ids)

    @api.depends("slip_ids.state")
    def _compute_state(self):
        for payslip_run in self:
            states = payslip_run.mapped('slip_ids.state')
            if any(state == "draft" for state in states) or not payslip_run.slip_ids:
                payslip_run.state = '01_ready'
            elif any(state == "validated" for state in states):
                payslip_run.state = '02_close'
            elif any(state == "paid" for state in states):
                payslip_run.state = '03_paid'
            elif all(state == "cancel" for state in states):
                payslip_run.state = '04_cancel'
            else:
                payslip_run.state = '01_ready'

    @api.depends('state')
    def _compute_color(self):
        for payslip_run in self:
            payslip_run.color = STATUS_COLOR[payslip_run.state]

    @api.depends('schedule_pay')
    def _compute_date_start(self):
        for payslip_run in self:
            if payslip_run.schedule_pay:
                payslip_run.date_start = self.env["hr.payslip"]._schedule_period_start(payslip_run.schedule_pay, date.today(), payslip_run.country_code)

    @api.depends('date_start')
    def _compute_date_end(self):
        for payslip_run in self:
            if payslip_run.schedule_pay:
                payslip_run.date_end = (payslip_run.date_start and payslip_run.date_start +
                                        self.env["hr.payslip"]._schedule_timedelta(payslip_run.schedule_pay, payslip_run.date_start, payslip_run.country_code))

    @api.depends("slip_ids.gross_wage", "slip_ids.net_wage", "slip_ids.state")
    def _compute_gross_net_sum(self):
        for payslip_run in self:
            payslip_run.gross_sum = sum(payslip_run.slip_ids.filtered(lambda p: p.state != "cancel").mapped("gross_wage"))
            payslip_run.net_sum = sum(payslip_run.slip_ids.filtered(lambda p: p.state != "cancel").mapped("net_wage"))

    @api.model_create_multi
    def create(self, vals_list):
        formated_date_cache = {}
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self._get_name_for_period(vals, formated_date_cache)
        return super().create(vals_list)

    @api.depends('slip_ids.error_count', 'slip_ids.warning_count')
    def _compute_payslips_with_issues(self):
        for run in self:
            run.payslips_with_issues = len(run.slip_ids.filtered(lambda ps: ps.error_count or ps.warning_count))

    @api.depends('slip_ids.error_count')
    def _compute_has_error(self):
        for run in self:
            run.has_error = bool(run.slip_ids.filtered('error_count'))

    @api.depends('slip_ids.line_ids')
    def _compute_empty_payslips(self):
        for run in self:
            run.empty_payslips = len(run.slip_ids.filtered(
                lambda slip: not slip.line_ids
            ))

    def action_draft(self):
        if self.slip_ids.filtered(lambda s: s.state == 'paid'):
            raise ValidationError(self.env._('You cannot reset a pay run to draft if some of the payslips have already been paid.'))
        self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'hr.payslip.run'),
            ('res_id', 'in', self.ids),
            ('res_field', '=', 'payment_report')
        ]).unlink()
        self.write({
            'payment_report': False,
            'payment_report_filename': False,
            'payment_report_format': False,
            'payment_report_date': False,
        })
        self.slip_ids.write({
            'state': 'draft',
        })

    def action_payment_report(self, export_format='csv'):
        self.ensure_one()
        self.env['hr.payroll.payment.report.wizard'].create([{
            'payslip_ids': self.slip_ids.ids,
            'payslip_run_id': self.id,
            'export_format': export_format
        }]).generate_payment_report()

    def action_paid(self):
        self.mapped('slip_ids').action_payslip_paid()

    def action_unpaid(self):
        self.slip_ids.action_payslip_unpaid()

    def action_validate(self):
        return self.slip_ids.filtered(
            lambda slip: slip.state != 'cancel' and slip.line_ids
        ).action_payslip_done()

    def action_confirm(self):
        self.slip_ids.filtered(lambda slip: slip.state == 'draft').compute_sheet()

    def action_open_payslips(self):
        action = self.env['ir.actions.act_window']._for_xml_id('hr_payroll.action_view_hr_payslip_month_form')
        action['context'] = dict(
            literal_eval(action["context"]),
            search_default_payslip_run_id=self.id or False)
        return action

    def action_payroll_hr_version_list_view_payrun(self, date_start=None, date_end=None, structure_id=None, company_id=None, schedule_pay=None):
        action = self.env['ir.actions.act_window']._for_xml_id('hr_payroll.action_payroll_hr_version_list_view_payrun')

        valid_version_ids = self._get_valid_version_ids(
            fields.Date.from_string(date_start),
            fields.Date.from_string(date_end),
            structure_id,
            company_id,
            None,
            schedule_pay,
        )

        payslip_domain = Domain.AND([
           Domain('version_id', 'in', valid_version_ids),
           Domain('date_from', '=', fields.Date.from_string(date_start) if date_start else self.date_start),
           Domain('date_to', '=', fields.Date.from_string(date_end) if date_end else self.date_end),
           Domain('struct_id', '=', structure_id if structure_id else (self.structure_id.id if self.structure_id else False)),
           Domain('state', '!=', 'cancel'),
           Domain('version_id.schedule_pay', '=', schedule_pay if schedule_pay else False)
        ])
        existing_version_ids = self.env['hr.payslip'].search(payslip_domain).version_id.ids
        filtered_version_ids = set(valid_version_ids) - set(existing_version_ids)
        action['domain'] = [("id", "in", list(filtered_version_ids))]
        return action

    def action_review_issues(self):
        self.ensure_one()
        return {
            'name': 'Issue Payslips',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'context': {
                'search_default_payslip_run_id': self.id,
                'search_default_filter_issue': 1,
            }
        }

    def generate_payslips(self, version_ids=None, employee_ids=None):
        self.ensure_one()

        if employee_ids and not version_ids:
            version_ids = self._get_valid_version_ids(employee_ids=employee_ids)

        if not version_ids:
            raise UserError(self.env._("You must select employee(s) version(s) to generate payslip(s)."))

        valid_versions = self.env["hr.version"].browse(version_ids)

        Payslip = self.env['hr.payslip']

        if self.structure_id:
            valid_versions = valid_versions.filtered(lambda c: c.structure_type_id.id == self.structure_id.type_id.id)
        valid_versions.generate_work_entries(self.date_start, self.date_end)

        all_work_entries = dict(self.env['hr.work.entry']._read_group(
            domain=[
                ('employee_id', 'in', valid_versions.employee_id.ids),
                ('date', '<=', self.date_end),
                ('date', '>=', self.date_start),
            ],
            groupby=['version_id'],
            aggregates=['id:recordset'],
        ))

        utc = pytz.utc
        for tz, slips_per_tz in self.slip_ids.grouped(lambda s: s.version_id.tz).items():
            slip_tz = pytz.timezone(tz or utc)
            for slip in slips_per_tz:
                date_from = slip_tz.localize(datetime.combine(slip.date_from, time.min)).astimezone(utc).replace(tzinfo=None)
                date_to = slip_tz.localize(datetime.combine(slip.date_to, time.max)).astimezone(utc).replace(tzinfo=None)
                if version_work_entries := all_work_entries.get(slip.version_id):
                    version_work_entries.filtered_domain([
                        ('date', '<=', date_to),
                        ('date', '>=', date_from),
                    ])
                    version_work_entries._check_undefined_slots(slip.date_from, slip.date_to)

        for work_entries in all_work_entries.values():
            work_entries = work_entries.filtered(lambda we: we.state != 'validated')
            if work_entries._check_if_error():
                work_entries = work_entries.filtered(lambda we: we.state == 'conflict')
                conflicts = work_entries._to_intervals()
                time_intervals_str = "".join(
                    f"\n - {start} -> {end} ({entry.employee_id.name})" for start, end, entry in conflicts._items)
                raise UserError(self.env._("Some work entries could not be validated. Time intervals to look for:%s", time_intervals_str))

        default_values = Payslip.default_get(Payslip.fields_get())
        payslips_vals = []
        for version in valid_versions[::-1]:
            values = default_values | {
                'name': self.env._('New Payslip'),
                'employee_id': version.employee_id.id,
                'payslip_run_id': self.id,
                'date_from': self.date_start,
                'date_to': self.date_end,
                'version_id': version.id,
                'company_id': self.company_id.id,
                'struct_id': self.structure_id.id or version.structure_type_id.default_struct_id.id,
            }
            payslips_vals.append(values)
        self.slip_ids |= Payslip.with_context(tracking_disable=True).create(payslips_vals)
        self.slip_ids._compute_name()
        self.slip_ids.compute_sheet()
        self.state = '01_ready'

        return 1

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft_or_cancel(self):
        if any(self.mapped('slip_ids').filtered(lambda payslip: payslip.state not in ('draft', 'cancel'))):
            raise UserError(self.env._("You can't delete a pay run with payslips if they are not draft or cancelled."))

    def _are_payslips_ready(self):
        return any(slip.state in ['validated', 'cancel'] for slip in self.mapped('slip_ids'))

    @api.model
    def get_unusual_days(self, date_from, date_to=None):
        return self.env.company.resource_calendar_id._get_unusual_days(
            datetime.combine(fields.Date.from_string(date_from), time.min).replace(tzinfo=pytz.utc),
            datetime.combine(fields.Date.from_string(date_to), time.max).replace(tzinfo=pytz.utc),
            self.company_id,
        )

    def get_formview_action(self, access_uid=None):
        return self.action_open_payslips()

    @api.depends('slip_ids.employer_cost')
    def _compute_total_employer_cost(self):
        for payslip_run in self:
            payslip_run.total_employer_cost = sum(payslip_run.slip_ids.mapped('employer_cost'))
