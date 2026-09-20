# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    _description = 'Employee'

    currency_id = fields.Many2one(
        "res.currency",
        string='Currency',
        related='company_id.currency_id')
    slip_ids = fields.One2many('hr.payslip', 'employee_id', string='Payslips', readonly=True, groups="hr_payroll.group_hr_payroll_user")
    payslip_count = fields.Integer(compute='_compute_payslip_count', string='Payslip Count', groups="hr_payroll.group_hr_payroll_user")
    registration_number = fields.Char('Employee Reference', groups="hr.group_hr_user", copy=False, tracking=True)
    salary_attachment_ids = fields.Many2many(
        'hr.salary.attachment',
        string='Salary Adjustments',
        groups="hr_payroll.group_hr_payroll_user")
    salary_attachment_count = fields.Integer(
        compute='_compute_salary_attachment_count', string="Salary Adjustment Count",
        groups="hr_payroll.group_hr_payroll_user")
    mobile_invoice = fields.Binary(string="Mobile Subscription Invoice", groups="hr.group_hr_manager")
    sim_card = fields.Binary(string="SIM Card Copy", groups="hr.group_hr_manager")
    internet_invoice = fields.Binary(string="Internet Subscription Invoice", groups="hr.group_hr_manager")
    schedule_pay = fields.Selection(readonly=False, related="version_id.schedule_pay", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    contract_date_start = fields.Date(readonly=False, related="version_id.contract_date_start", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    contract_date_end = fields.Date(readonly=False, related="version_id.contract_date_end", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    trial_date_end = fields.Date(readonly=False, related="version_id.trial_date_end", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    wage = fields.Monetary(readonly=False, related="version_id.wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    contract_wage = fields.Monetary(related="version_id.contract_wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    work_entry_source = fields.Selection(readonly=False, related="version_id.work_entry_source", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    work_entry_source_calendar_invalid = fields.Boolean(groups="hr_payroll.group_hr_payroll_user")
    wage_type = fields.Selection(readonly=False, related="version_id.wage_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    hourly_wage = fields.Monetary(readonly=False, related="version_id.hourly_wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    payslips_count = fields.Integer(related="version_id.payslips_count", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    work_time_rate = fields.Float(related="version_id.work_time_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    disabled = fields.Boolean(readonly=False, related="version_id.disabled", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    date_start = fields.Date(related="version_id.date_start", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    date_end = fields.Date(related="version_id.date_end", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    is_current = fields.Boolean(related="version_id.is_current", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    is_past = fields.Boolean(related="version_id.is_past", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    is_future = fields.Boolean(related="version_id.is_future", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    is_in_contract = fields.Boolean(related="version_id.is_in_contract", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    structure_type_id = fields.Many2one(related="version_id.structure_type_id", inherited=True, store=True, groups="hr_payroll.group_hr_payroll_user")
    contract_type_id = fields.Many2one(related="version_id.contract_type_id", inherited=True, store=True, groups="hr_payroll.group_hr_payroll_user")
    structure_id = fields.Many2one(related="version_id.structure_id", inherited=True, groups="hr.group_hr_user")
    payroll_properties = fields.Properties(readonly=False, related="version_id.payroll_properties", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    monthly_running_attachments = fields.Monetary(
        compute='_compute_monthly_running_attachments',
        groups="hr_payroll.group_hr_payroll_user")

    _unique_registration_number = models.Constraint(
        'UNIQUE(registration_number, company_id)',
        "No duplication of registration numbers is allowed",
    )

    def _compute_payslip_count(self):
        for employee in self:
            employee.payslip_count = len(employee.slip_ids)

    def _compute_salary_attachment_count(self):
        for employee in self:
            employee.salary_attachment_count = len(employee.salary_attachment_ids)

    def _compute_monthly_running_attachments(self):
        for employee in self:
            running_attachment_ids = employee.salary_attachment_ids.filtered(lambda a: a.state == 'open')
            employee.monthly_running_attachments = sum(running_attachment_ids.mapped("monthly_amount"))

    def action_open_payslips(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr_payroll.action_view_hr_payslip_month_form")
        action.update({
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'search_default_group_by_version_id': 1,
                'default_employee_id': self.id,
            },
        })
        return action

    def action_open_salary_attachments(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr_payroll.hr_salary_attachment_action")
        action.update({'domain': [('employee_ids', 'in', self.ids)],
                       'context': {'default_employee_ids': self.ids}})
        return action

    def _index_employee_contracts(self, multi_employees=False):
        action = self.env["ir.actions.actions"]._for_xml_id("hr_payroll.action_hr_payroll_index")
        if not multi_employees:
            action['context'] = ({
                'default_version_ids': self.version_id.ids,
                'active_employee_id': self.id,
            })
        else:
            action['context'] = {'default_employee_ids': self.ids}
        return action

    @api.model
    def _get_account_holder_employees_data(self):
        # as acc_type isn't stored we can not use a domain to retrieve the employees
        # bypass orm for performance, we only care about the employee id anyway

        # return nothing if user has no right to either employee or bank partner
        if (not self.browse().has_access('read') or
                not self.env['res.partner.bank'].has_access('read')):
            return []

        self.env.cr.execute('''
            SELECT emp.id,
                   acc.acc_number,
                   acc.allow_out_payment
             FROM  hr_employee emp
         LEFT JOIN employee_bank_account_rel rel
                ON rel.employee_id=emp.id
         LEFT JOIN res_partner_bank acc
                ON acc.id=rel.bank_account_id
              JOIN hr_version ver
                ON ver.employee_id=emp.id
             WHERE emp.company_id IN %s
             AND emp.active = TRUE
        ''', (tuple(self.env.companies.ids),))

        return self.env.cr.dictfetchall()

    @api.model
    def _get_untrusted_bank_account_ids(self):
        """Return a list of bank account IDs linked to employees that are not marked for out payment."""
        if (not self.browse().has_access('read') or
                not self.env['res.partner.bank'].has_access('read')):
            return []

        self.env.cr.execute('''
            SELECT acc.id
            FROM res_partner_bank acc
            JOIN employee_bank_account_rel rel
                ON rel.bank_account_id = acc.id
            JOIN hr_employee emp
                ON emp.id = rel.employee_id
            WHERE acc.allow_out_payment = FALSE
            AND emp.company_id IN %s
            AND emp.active = TRUE
        ''', (tuple(self.env.companies.ids),))
        # Return ids of untrusted bank accounts.
        return [row[0] for row in self.env.cr.fetchall()]

    def action_configure_employee_inputs(self):
        self.ensure_one()
        return self.structure_id.action_get_structure_inputs()
