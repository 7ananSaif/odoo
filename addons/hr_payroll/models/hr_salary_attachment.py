# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_amount
from odoo.tools.date_utils import start_of
from odoo.tools.misc import formatLang

from dateutil.relativedelta import relativedelta
from math import ceil


class HrSalaryAttachment(models.Model):
    _name = 'hr.salary.attachment'
    _description = 'Salary Adjustment'
    _inherit = ['mail.thread']
    _rec_name = 'description'

    _check_monthly_amount = models.Constraint(
        'CHECK (monthly_amount > 0)',
        'Oops! Let’s keep the payslip amount strictly positive. We want to deduct money from our employee’s payslip, not add to it!'
    )
    _check_total_amount = models.Constraint(
        "CHECK ((total_amount > 0 AND total_amount >= monthly_amount) OR duration_type = 'unlimited')",
        "Total amount must be strictly positive and greater than or equal to the payslip amount.",
    )
    _check_remaining_amount = models.Constraint(
        'CHECK (remaining_amount >= 0)',
        "Remaining amount must be positive.",
    )
    _check_dates = models.Constraint(
        'CHECK (date_start <= date_end)',
        "End date may not be before the starting date.",
    )

    employee_ids = fields.Many2many('hr.employee', string='Employees', required=True,
                                    domain=lambda self: [('company_id', 'in', self.env.companies.ids)])
    employee_count = fields.Integer(compute='_compute_employee_count')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    description = fields.Char(string="Note")
    other_input_type_id = fields.Many2one(
        'hr.payslip.input.type',
        string="Type",
        required=True,
        tracking=True,
        domain=[('available_in_attachments', '=', True)]
    )
    duration_type = fields.Selection(
        selection=[
            ('one', 'One Time'),
            ('limited', 'Limited'),
            ('unlimited', 'Unlimited'),
        ],
        compute="_compute_duration_type",
        string='Duration',
        default='one',
        store=True,
        required=True,
        readonly=False,
    )
    monthly_amount = fields.Monetary('Payslip Amount', required=True, tracking=True, help='Amount to pay each payslip.')
    monthly_amount_display = fields.Char('Payslip Amount Display', compute="_compute_monthly_amount_display")
    occurrences = fields.Integer(
        compute='_compute_occurrences',
        help='Number of times the salary adjustment will appear on the payslip.',
    )
    active_amount = fields.Monetary(
        'Active Amount', compute='_compute_active_amount',
        help='Amount to pay for this payslip, Payslip Amount or less depending on the Remaining Amount.',
    )
    total_amount = fields.Monetary(
        'Total Amount',
        tracking=True,
        compute='_compute_total_amount',
        readonly=False,
        store=True,
        help='Total amount to be paid.',
    )
    total_amount_display = fields.Char('Total Amount Display', compute="_compute_total_amount_display")
    has_total_amount = fields.Boolean('Has Total Amount', compute='_compute_has_total_amount')
    paid_amount = fields.Monetary('Paid Amount', tracking=True, copy=False)
    remaining_time = fields.Char(
        'Remaining Time', compute='_compute_remaining_time', help='Remaining time to be paid.'
    )
    remaining_amount = fields.Monetary(
        'Remaining Amount', compute='_compute_remaining_amount', store=True,
        help='Remaining amount to be paid.',
    )
    is_quantity = fields.Boolean(related='other_input_type_id.is_quantity')
    is_refund = fields.Boolean(
        string='Negative Value',
        help='Check if the value of the salary adjustment must be taken into account as negative (-X)')
    date_start = fields.Date('Start Date', required=True, default=lambda r: start_of(fields.Date.today(), 'month'), tracking=True)
    date_estimated_end = fields.Date(
        'Estimated End Date', compute='_compute_estimated_end',
        help='Approximated end date.',
    )
    date_end = fields.Date(
        'End Date', default=False, tracking=True,
        help='Date at which this assignment has been set as completed.',
    )
    state = fields.Selection(
        selection=[
            ('open', 'Running'),
            ('close', 'Closed'),
        ],
        string='Status',
        default='open',
        required=True,
        tracking=True,
        copy=False,
    )
    payslip_ids = fields.Many2many('hr.payslip', relation='hr_payslip_hr_salary_attachment_rel', string='Payslips', copy=False)
    payslip_count = fields.Integer('# Payslips', compute='_compute_payslip_count')
    has_done_payslip = fields.Boolean(compute="_compute_has_done_payslip")

    attachment = fields.Binary('Document', copy=False)
    attachment_name = fields.Char()

    has_similar_attachment = fields.Boolean(compute='_compute_has_similar_attachment')
    has_similar_attachment_warning = fields.Char(compute='_compute_has_similar_attachment')

    @api.depends('other_input_type_id', "duration_type")
    def _compute_display_name(self):
        for attachment in self:
            attachment.display_name = self.env._(
                "%(display_name)s %(duration_type)s",
                display_name=attachment.other_input_type_id.display_name,
                duration_type=dict(self._fields['duration_type']._description_selection(self.env))[attachment.duration_type]
            )

    @api.depends("other_input_type_id")
    def _compute_duration_type(self):
        for attachment in self:
            if attachment.other_input_type_id.default_no_end_date:
                attachment.duration_type = 'unlimited'

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for attachment in self:
            attachment.employee_count = len(attachment.employee_ids)

    @api.depends('has_total_amount', 'monthly_amount', 'date_start', 'date_end')
    def _compute_total_amount(self):
        for record in self:
            if record.has_total_amount and record.duration_type != 'one':
                if record.total_amount:
                    continue
                date_start = record.date_start if record.date_start else fields.Date.today()
                date_end = record.date_end if record.date_end else fields.Date.today()
                month_difference = (date_end.year - date_start.year) * 12 + (date_end.month - date_start.month)
                record.total_amount = max(0, month_difference + 1) * record.monthly_amount
            else:
                record.total_amount = record.monthly_amount

    @api.depends('monthly_amount', 'is_quantity')
    def _compute_monthly_amount_display(self):
        for attachment in self:
            sign = -1 if attachment.is_refund else 1
            if attachment.is_quantity:
                attachment.monthly_amount_display = sign * attachment.total_amount
            else:
                attachment.monthly_amount_display = format_amount(self.env, sign * attachment.monthly_amount, attachment.currency_id)

    @api.depends('total_amount', 'duration_type', 'is_quantity')
    def _compute_total_amount_display(self):
        for attachment in self:
            if attachment.duration_type == 'unlimited':
                attachment.total_amount_display = self.env._('Indefinite')
            elif attachment.is_quantity:
                attachment.total_amount_display = attachment.total_amount
            else:
                attachment.total_amount_display = format_amount(self.env, attachment.total_amount, attachment.currency_id)

    @api.depends('monthly_amount', 'total_amount')
    def _compute_occurrences(self):
        self.occurrences = 0
        for attachment in self:
            if not attachment.total_amount or not attachment.monthly_amount:
                continue
            attachment.occurrences = ceil(attachment.total_amount / attachment.monthly_amount)

    @api.depends('duration_type', 'date_end')
    def _compute_has_total_amount(self):
        for record in self:
            if record.duration_type == "unlimited" and not record.date_end:
                record.has_total_amount = False
            else:
                record.has_total_amount = True

    @api.depends('duration_type', 'date_end', 'date_estimated_end')
    def _compute_remaining_time(self):
        for attachment in self:
            date_end = attachment.date_estimated_end or attachment.date_end
            if attachment.duration_type in ["unlimited", "one"] or not date_end:
                attachment.remaining_time = False
            else:
                delta = relativedelta(date_end, fields.Date.today().replace(day=1))
                if delta:
                    if delta.years:
                        attachment.remaining_time = self.env._("%(years)s years", years=delta.years)
                    elif delta.months:
                        attachment.remaining_time = self.env._("%(months)s months", months=delta.months)
                    else:
                        attachment.remaining_time = self.env._("few days")
                else:
                    attachment.remaining_time = False

    @api.depends('total_amount', 'paid_amount', 'monthly_amount')
    def _compute_remaining_amount(self):
        for record in self:
            if record.has_total_amount:
                record.remaining_amount = max(0, record.total_amount - record.paid_amount)
            else:
                record.remaining_amount = record.monthly_amount

    @api.depends('state', 'total_amount', 'monthly_amount', 'date_start')
    def _compute_estimated_end(self):
        for record in self:
            if record.state != 'close' and record.has_total_amount and record.monthly_amount:
                record.date_estimated_end = start_of(record.date_start + relativedelta(months=ceil(record.remaining_amount / record.monthly_amount)), 'month')
            else:
                record.date_estimated_end = False

    @api.depends('payslip_ids')
    def _compute_payslip_count(self):
        for record in self:
            record.payslip_count = len(record.payslip_ids)

    @api.depends('total_amount', 'paid_amount', 'monthly_amount')
    def _compute_active_amount(self):
        for record in self:
            record.active_amount = min(record.monthly_amount, record.remaining_amount)

    @api.depends('employee_ids', 'monthly_amount', 'date_start', 'duration_type', 'other_input_type_id', 'is_refund', 'total_amount')
    def _compute_has_similar_attachment(self):
        date_min = min(self.mapped('date_start'))
        possible_matches = self.search([
            ('state', '=', 'open'),
            ('employee_ids', 'in', self.employee_ids.ids),
            ('monthly_amount', 'in', self.mapped('monthly_amount')),
            ('total_amount', 'in', self.mapped('total_amount')),
            ('date_start', '<=', date_min),
        ])
        for record in self:
            similar = []
            if record.employee_count == 1 and record.date_start and record.state == 'open':
                similar = possible_matches.filtered_domain([
                    ('id', '!=', record.id or record._origin.id),
                    ('employee_ids', 'in', record.employee_ids.ids),
                    ('monthly_amount', '=', record.monthly_amount),
                    ('duration_type', '=', record.duration_type),
                    ('is_refund', '=', record.is_refund),
                    ('total_amount', '=', record.total_amount),
                    ('date_start', '<=', record.date_start),
                    ('other_input_type_id', '=', record.other_input_type_id.id),
                ])
                similar = similar.filtered(lambda s: s.employee_count == 1)
            record.has_similar_attachment = similar if record.state == 'open' else False
            record.has_similar_attachment_warning = similar and self.env._('Warning, a similar attachment has been found.')

    @api.depends("payslip_ids.state")
    def _compute_has_done_payslip(self):
        for record in self:
            record.has_done_payslip = any(payslip.state in ['validated', 'paid'] for payslip in record.payslip_ids)

    def action_close(self):
        self.write({
            'state': 'close',
            'date_end': fields.Date.today(),
        })

    def action_split(self):
        self.ensure_one()
        if self.employee_count > 1:
            description = self.description
            salary_attachments = self.env['hr.salary.attachment'].create([{
                'employee_ids': [(4, employee.id)],
                'company_id': self.company_id.id,
                'description': self.description,
                'other_input_type_id': self.other_input_type_id.id,
                'duration_type': self.duration_type,
                'monthly_amount': self.monthly_amount,
                'total_amount': self.total_amount,
                'paid_amount': self.paid_amount,
                'date_start': self.date_start,
                'date_end': self.date_end,
                'state': 'open',
                'attachment': self.attachment,
                'attachment_name': self.attachment_name,
            } for employee in self.employee_ids])
            employee = self.env.context.get('default_employee_ids')
            self.write({'state': 'close'})
            if employee:
                employee_index = self.employee_ids.ids.index(employee[0])
                self.unlink()
                return {
                'type': 'ir.actions.act_window',
                'name': self.env._('Edit Individual Salary Adjustment'),
                'view_mode': 'form',
                'view_id': self.env.ref("hr_payroll.hr_salary_attachment_employee_view_form").id,
                'res_id': salary_attachments[employee_index].id,
                'res_model': 'hr.salary.attachment',
                'target': 'new',
                'context': {**self.env.context}
                }
            self.unlink()
            return {
                'type': 'ir.actions.act_window',
                'name': self.env._('Salary Adjustments'),
                'res_model': 'hr.salary.attachment',
                'domain': [('id', 'in', salary_attachments.ids)],
                'view_mode': 'list,form',
                'context': {'search_default_description': description},
            }
        raise UserError(self.env._("You can only split a salary adjustment if it has more than one employee."))

    def action_open(self):
        self.ensure_one()
        self.write({
            'state': 'open',
            'date_end': False,
        })

    def action_open_payslips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Payslips'),
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.payslip_ids.ids)],
        }

    def action_unlink(self):
        self.ensure_one()
        if self.employee_count > 1:
            self.employee_ids = self.employee_ids.filtered(lambda e: e.id not in self.env.context.get('default_employee_ids', []))
        else:
            self.unlink()
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def action_open_employee_salary_attachment(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('New Salary Adjustment') if self.env.context.get("new") else self.env._('Edit Salary Adjustment'),
            'views': [[self.env.ref("hr_payroll.hr_salary_attachment_employee_view_form").id, "form"]],
            'res_id': False if self.env.context.get("new") else self.id,
            'target': "new",
            'res_model': 'hr.salary.attachment',
            'context': {
                **self.env.context,
            }
        }

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_running(self):
        if any(assignment.state == 'open' for assignment in self):
            raise UserError(self.env._(
                "The salary adjustment you're trying to remove is still running. You can’t delete unless you change it to completed or cancelled."
            ))

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_linked_in_payslips(self):
        if any(attachment.payslip_ids for attachment in self):
            raise UserError(self.env._('You cannot delete a salary adjustment that is linked to a payslip!'))

    def record_payment(self, total_amount):
        ''' Record a new payment for this attachment, if the total has been reached the attachment will be closed.

        :param total_amount: amount to register for this payment
            computed using the payslip_amount and the total if not given

        Note that paid_amount can never be higher than total_amount
        '''
        def _record_payment(attachment, amount):
            attachment.message_post(
                body=self.env._('Recorded a new payment of %s.', formatLang(self.env, amount, currency_obj=attachment.currency_id))
            )
            attachment.paid_amount += amount
            if attachment.remaining_amount == 0:
                attachment.action_close()

        if any(len(a.employee_ids) > 1 for a in self):
            raise UserError(self.env._('You cannot record a payment on multi employees attachments.'))

        remaining = total_amount
        # It is necessary to sort attachments to pay monthly payments (child_support) first
        attachments_sorted = self.sorted(key=lambda a: a.has_total_amount)
        # For all types of attachments, we must pay the payslip_amount without exceeding the total amount
        for attachment in attachments_sorted:
            amount = min(attachment.monthly_amount, attachment.remaining_amount, remaining)
            if not amount:
                continue
            remaining -= amount
            _record_payment(attachment, amount)
        # If we still have remaining, balance the attachments (running) that have a total amount
        # in the chronology of estimated end dates.
        if remaining:
            fixed_total_attachments = self.filtered(lambda a: a.state == 'open' and a.has_total_amount)
            fixed_total_attachments_sorted = fixed_total_attachments.sorted(lambda a: a.date_estimated_end)
            for attachment in fixed_total_attachments_sorted:
                amount = min(attachment.remaining_amount, attachment.remaining_amount, remaining)
                if not amount:
                    continue
                remaining -= amount
                _record_payment(attachment, amount)

    def _get_active_amount(self):
        return sum(a.active_amount * (-1 if a.is_refund else 1) for a in self)
