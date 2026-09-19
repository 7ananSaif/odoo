# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipEmployeeDepatureHolidayAttests(models.TransientModel):
    _name = 'hr.payslip.employee.depature.holiday.attests'
    _description = 'Manage the Employee Departure Holiday Attests'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "BE":
            raise UserError(_('This feature seems to be as exclusive as Belgian chocolates. You must be logged in to a Belgian company to use it.'))
        return super().default_get(fields)

    employee_id = fields.Many2one('hr.employee', string='Employee', default=lambda self: self.env.context.get('active_id'), domain="[('company_id', 'in', allowed_company_ids)]")

    payslip_n_ids = fields.Many2many(
        'hr.payslip', string='Payslips N', relation='holiday_attest_payslip_n_rel',
        compute='_compute_payslip_history', store=True, readonly=False)
    number_n_payslips_description = fields.Char(compute='_compute_number_n_payslips_description')
    payslip_n1_ids = fields.Many2many(
        'hr.payslip', string='Payslips N-1', relation='holiday_attest_payslip_n1_rel',
        compute='_compute_payslip_history', store=True, readonly=False)
    number_n1_payslips_description = fields.Char(compute='_compute_number_n1_payslips_description')
    currency_id = fields.Many2one(related='employee_id.version_id.currency_id')
    net_n = fields.Monetary('Gross Annual Remuneration Current Year', compute='_compute_net_n', store=True,
        readonly=False, help="""
        Taking into account for remuneration:
            - Fixed and variable remuneration
            - Overtime worked
            - Benefits in kind and bonuses
            - Remuneration of statutory holidays occurring within 30 days of the end date of the contract
            - End-of-year bonus, 13th month or other similar amount
            - Beneficiary holdings
            - Various bonuses
        We draw your attention to the fact that this information is based on the data in Odoo and / or that you
        have introduced in Odoo and that it is important that they be accompanied by a verification on your part
        according to the particularities related to contract of the worker or your company which Odoo would not
        know.
        """
    )
    net_n1 = fields.Monetary(
        'Gross Annual Remuneration Previous Year',
        compute='_compute_net_n1', store=True, readonly=False)
    fictitious_remuneration_n = fields.Monetary(
        'Remuneration fictitious current year', compute='_compute_fictitious_remuneration_n')
    fictitious_remuneration_n1 = fields.Monetary(
        'Remuneration fictitious previous year', compute='_compute_fictitious_remuneration_n1')
    gross_reference_remuneration_n = fields.Monetary(
        'Gross reference remuneration current year', compute='_compute_gross_reference_remuneration_n')
    gross_reference_remuneration_n1 = fields.Monetary(
        'Gross reference remuneration previous year', compute='_compute_gross_reference_remuneration_n1')

    time_off_line_ids = fields.One2many('hr.payslip.employee.depature.holiday.attests.time.off.line',
        'wizard_id', string="Time Off", compute='_compute_time_off_line_ids', readonly=False, store=True)

    @api.depends('employee_id')
    def _compute_payslip_history(self):
        for wizard in self:
            if wizard.employee_id and (not wizard.employee_id.start_notice_period or not wizard.employee_id.end_notice_period):
                raise UserError(_("Notice period not set for %s. Please, set the departure notice period first.", wizard.employee_id.name))

            if not wizard.employee_id:
                wizard.update({
                    'payslip_n_ids': [(5, 0, 0)],
                    'payslip_n1_ids': [(5, 0, 0)],
                })
                continue

            current_year = wizard.employee_id.end_notice_period.replace(month=1, day=1)
            previous_year = current_year + relativedelta(years=-1)

            structure_warrant = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_structure_warrant')
            structure_double_holidays = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday')
            structure_termination = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
            structure_holidays_n = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')
            structure_holidays_n1 = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')

            payslip_n_ids = self.env['hr.payslip'].search([
                ('employee_id', '=', wizard.employee_id.id),
                ('date_to', '>=', current_year),
                ('state', 'in', ['validated', 'paid', 'draft']),
                ('struct_id', 'not in', (structure_warrant + structure_double_holidays + structure_termination + structure_holidays_n + structure_holidays_n1).ids)])
            payslip_n1_ids = self.env['hr.payslip'].search([
                ('employee_id', '=', wizard.employee_id.id),
                ('date_to', '>=', previous_year),
                ('date_from', '<', current_year),
                ('state', 'in', ['validated', 'paid']),
                ('struct_id', 'not in', (structure_warrant + structure_double_holidays + structure_termination + structure_holidays_n + structure_holidays_n1).ids)])

            wizard.payslip_n_ids = [(4, p.id) for p in payslip_n_ids]
            wizard.payslip_n1_ids = [(4, p.id) for p in payslip_n1_ids]

    @api.depends('employee_id')
    def _compute_time_off_line_ids(self):
        for wizard in self:
            if wizard.employee_id and (not wizard.employee_id.start_notice_period or not wizard.employee_id.end_notice_period):
                raise UserError(_("Notice period not set for %s. Please, set the departure notice period first.", wizard.employee_id.name))

            if not wizard.employee_id:
                wizard.update({
                    'time_off_line_ids': [(5, 0, 0)],
                })
                continue

            current_year = wizard.employee_id.end_notice_period.replace(month=1, day=1)

            target_leave_types = self.env['hr.leave.type'].search([
                ('work_entry_type_id', 'in', (
                    self.env.ref('hr_work_entry.work_entry_type_legal_leave').id,
                    self.env.ref('hr_work_entry.l10n_be_work_entry_type_european').id,
                ))
            ]).ids

            time_off_ids = self.env['hr.leave'].search([
                ('employee_id', '=', wizard.employee_id.id),
                ('date_from', '>=', current_year),
                ('state', '=', 'validate'),
                ('holiday_status_id', 'in', target_leave_types)])

            time_off_allocation_ids = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', wizard.employee_id.id),
                ('date_from', '>=', current_year),
                ('state', '=', 'validate'),
                ('holiday_status_id', 'in', target_leave_types)])

            values = []
            for time_off_type_id in target_leave_types:
                time_offs = time_off_ids.filtered(
                    lambda t: t.holiday_status_id.id == time_off_type_id
                )
                time_off_allocations = time_off_allocation_ids.filtered(
                    lambda t: t.holiday_status_id.id == time_off_type_id
                )
                if time_offs or time_off_allocations:
                    values.append(
                        (0, 0, {
                            'year': current_year.year,
                            'leave_type_id': self.env['hr.leave.type'].browse(time_off_type_id).id,
                            'leave_allocation_count': sum(time_off_allocations.mapped('number_of_days')),
                            'leave_count': sum(time_offs.mapped('number_of_days')),
                        })
                    )

            wizard.write({
                'time_off_line_ids': values
            })

    @api.depends('payslip_n1_ids')
    def _compute_number_n1_payslips_description(self):
        for wizard in self:
            wizard.number_n1_payslips_description = self.env._("(%s payslips)", len(wizard.payslip_n1_ids))

    @api.depends('payslip_n_ids')
    def _compute_number_n_payslips_description(self):
        for wizard in self:
            wizard.number_n_payslips_description = self.env._("(%s payslips)", len(wizard.payslip_n_ids))

    @api.depends('payslip_n_ids')
    def _compute_net_n(self):
        for wizard in self:
            if wizard.payslip_n_ids:
                wizard.net_n = wizard.payslip_n_ids._origin._get_line_values(['SALARY'], compute_sum=True)['SALARY']['sum']['total']
            else:
                wizard.net_n = 0

    @api.depends('payslip_n1_ids')
    def _compute_net_n1(self):
        for wizard in self:
            if wizard.payslip_n1_ids:
                wizard.net_n1 = wizard.payslip_n1_ids._origin._get_line_values(['SALARY'], compute_sum=True)['SALARY']['sum']['total']
            else:
                wizard.net_n1 = 0

    @api.model
    def _get_last_year_variable_revenue(self, date_from):
        first_version_date = self.employee_id._get_first_version_date()
        if not first_version_date:
            return 0
        start = first_version_date
        end = date_from + relativedelta(day=31, months=-1)
        number_of_month = (end.year - start.year) * 12 + (end.month - start.month) + 1
        number_of_month = min(12, number_of_month)
        if number_of_month <= 0:
            return 0
        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', date_from + relativedelta(months=-12, day=1)),
            ('date_from', '<=', date_from),
        ], order="date_from asc")
        total_amount = payslips._get_line_values(['COMMISSION'], compute_sum=True)['COMMISSION']['sum']['total']
        return total_amount / number_of_month if number_of_month else 0

    @api.depends('payslip_n_ids')
    def _compute_fictitious_remuneration_n(self):
        for wizard in self:
            if wizard.employee_id and (not wizard.employee_id.start_notice_period or not wizard.employee_id.end_notice_period):
                raise UserError(_("Notice period not set for %s. Please, set the departure notice period first.", wizard.employee_id.name))
            if not wizard.employee_id:
                wizard.fictitious_remuneration_n = 0
                continue
            equivalent_number_of_days = sum(wizard.payslip_n_ids.worked_days_line_ids.filtered(
                lambda wd: not wd.is_paid and wd.code not in wizard.employee_id._get_l10n_be_holiday_attest_non_equivalent_codes() + ['OUT']
            ).mapped('number_of_days'))
            version_n = wizard.employee_id._get_version(wizard.employee_id.end_notice_period)
            fixed_monthly_salary = version_n._get_contract_wage()
            variable_monthly_salary = self._get_last_year_variable_revenue(wizard.employee_id.end_notice_period)
            wizard.fictitious_remuneration_n = equivalent_number_of_days * (fixed_monthly_salary + variable_monthly_salary) * 3 / 13 / 5

    @api.depends('payslip_n1_ids')
    def _compute_fictitious_remuneration_n1(self):
        for wizard in self:
            if wizard.employee_id and (not wizard.employee_id.start_notice_period or not wizard.employee_id.end_notice_period):
                raise UserError(_("Notice period not set for %s. Please, set the departure notice period first.", wizard.employee_id.name))
            if not wizard.employee_id:
                wizard.fictitious_remuneration_n1 = 0
                continue
            equivalent_number_of_days = sum(wizard.payslip_n1_ids.worked_days_line_ids.filtered(
                lambda wd: not wd.is_paid and wd.code not in wizard.employee_id._get_l10n_be_holiday_attest_non_equivalent_codes() + ['OUT']
            ).mapped('number_of_days'))
            last_day_previous_year = wizard.employee_id.end_notice_period.replace(month=12, day=31) - relativedelta(years=1)
            version_n1 = wizard.employee_id._get_version(last_day_previous_year)
            fixed_monthly_salary = version_n1._get_contract_wage()
            variable_monthly_salary = self._get_last_year_variable_revenue(last_day_previous_year)
            wizard.fictitious_remuneration_n1 = equivalent_number_of_days * (fixed_monthly_salary + variable_monthly_salary) * 3 / 13 / 5

    @api.depends('net_n', 'fictitious_remuneration_n')
    def _compute_gross_reference_remuneration_n(self):
        for wizard in self:
            wizard.gross_reference_remuneration_n = wizard.net_n + wizard.fictitious_remuneration_n

    @api.depends('net_n1', 'fictitious_remuneration_n1')
    def _compute_gross_reference_remuneration_n1(self):
        for wizard in self:
            wizard.gross_reference_remuneration_n1 = wizard.net_n1 + wizard.fictitious_remuneration_n1

    def compute_termination_holidays(self):
        struct_n1_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')
        struct_n_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')

        termination_payslip_n = self.env['hr.payslip'].create({
            'name': '%s - %s' % (struct_n_id.payslip_name, self.employee_id.legal_name),
            'employee_id': self.employee_id.id,
            'version_id': self.employee_id.version_id.id,
            'struct_id': struct_n_id.id,
            'date_from': (self.employee_id.version_id.contract_date_end or fields.Date.today()) + relativedelta(day=1),
            'date_to': (self.employee_id.version_id.contract_date_end or fields.Date.today()) + relativedelta(day=31),
        })
        termination_payslip_n.worked_days_line_ids = [(5, 0, 0)]

        monthly_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['validated', 'paid']),
            ('credit_note', '=', False),
            ('struct_id', '=', self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id)
        ], order="date_from desc").filtered(
            lambda p: 'OUT' not in p.worked_days_line_ids.mapped('code'))

        if monthly_payslips:
            slip = monthly_payslips[0]
            annual_gross = slip._get_line_values(['GROSS'])['GROSS'][slip.id]['total'] * 12
        else:
            annual_gross = 0

        # As regards the recovery of amounts for European holidays (“additional holidays”), the
        # amount paid in advance is
        # - or recovered from the double vacation pay (part 85%) for the following year;
        # - or, when the worker leaves, on the amount of the exit pay. The legislation does not
        # specifically state whether, in the event of an exit, the recovery is on the single or
        # the double, but, in order to be consistent, I would do the recovery on the double
        # (85% of 7.67 %).
        # In addition, when "additional" vacation has been taken, the vacation certificate must
        # mention: the number of days already granted + the related gross allowance.
        current_year_start = self.employee_id.end_notice_period.replace(month=1, day=1)
        current_year_end = self.employee_id.end_notice_period.replace(month=12, day=31)
        payslips_n = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '>=', current_year_start),
            ('date_to', '<=', current_year_end),
            ('state', 'in', ['draft', 'validated', 'paid'])])
        european_wds = payslips_n.worked_days_line_ids.filtered(lambda wd: wd.code == 'LEAVE216')
        european_leaves_amount = sum(european_wds.mapped('amount'))
        european_leaves_days = sum(european_wds.mapped('number_of_days'))
        european_amount_to_deduct = max(european_leaves_amount, 0)

        self.env['hr.payslip.input'].create([{
            'payslip_id': termination_payslip_n.id,
            'sequence': 2,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_gross_ref').id,
            'amount': self.gross_reference_remuneration_n,
            'version_id': termination_payslip_n.version_id.id
        }, {
            'payslip_id': termination_payslip_n.id,
            'sequence': 3,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_allocation').id,
            'amount': 0,
            'version_id': termination_payslip_n.version_id.id
        }, {
            'payslip_id': termination_payslip_n.id,
            'sequence': 4,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_time_off_taken').id,
            'amount': 0,
            'version_id': termination_payslip_n.version_id.id
        }, {
            'payslip_id': termination_payslip_n.id,
            'sequence': 5,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_annual_taxable_amount').id,
            'amount': annual_gross,
            'version_id': termination_payslip_n.version_id.id
        }, {
            'payslip_id': termination_payslip_n.id,
            'sequence': 6,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_european_leave').id,
            'amount': european_amount_to_deduct,
            'version_id': termination_payslip_n.version_id.id
        }, {
            'payslip_id': termination_payslip_n.id,
            'sequence': 7,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_european_leave_days').id,
            'amount': european_leaves_days,
            'version_id': termination_payslip_n.version_id.id
        }])
        termination_payslip_n.compute_sheet()
        termination_payslip_n.name = '%s - %s' % (struct_n_id.payslip_name, self.employee_id.legal_name)

        termination_payslip_n1 = self.env['hr.payslip'].create({
            'name': '%s - %s' % (struct_n1_id.payslip_name, self.employee_id.legal_name),
            'employee_id': self.employee_id.id,
            'version_id': self.employee_id.version_id.id,
            'struct_id': struct_n1_id.id,
            'date_from': (self.employee_id.version_id.contract_date_end or fields.Date.today()) + relativedelta(day=1),
            'date_to': (self.employee_id.version_id.contract_date_end or fields.Date.today()) + relativedelta(day=31),
        })
        termination_payslip_n1.worked_days_line_ids = [(5, 0, 0)]

        # As regards the recovery of amounts for European holidays (“additional holidays”), the
        # amount paid in advance is
        # - or recovered from the double vacation pay (part 85%) for the following year;
        # - or, when the worker leaves, on the amount of the exit pay. The legislation does not
        # specifically state whether, in the event of an exit, the recovery is on the single or
        # the double, but, in order to be consistent, I would do the recovery on the double
        # (85% of 7.67 %).
        # In addition, when "additional" vacation has been taken, the vacation certificate must
        # mention: the number of days already granted + the related gross allowance.
        current_year = self.employee_id.end_notice_period.replace(month=1, day=1)
        previous_year = current_year + relativedelta(years=-1)
        double_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday')
        double_holiday_n = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_to', '>=', current_year),
            ('state', 'in', ['validated', 'paid', 'draft']),
            ('struct_id', '=', double_structure.id)])
        # Part already deducted on the double holiday for year N
        double_amount_n = -double_holiday_n._get_line_values(['EU.LEAVE.DEDUC'], compute_sum=True)['EU.LEAVE.DEDUC']['sum']['total']
        # Original Amount to deduct
        payslip_n1 = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_to', '>=', previous_year),
            ('date_from', '<', current_year),
            ('state', 'in', ['validated', 'paid'])])
        legal_time_off_types = self.env['hr.leave.type'].search([
            ('work_entry_type_id', '=', self.env.ref('hr_work_entry.work_entry_type_legal_leave').id)
        ]).ids
        legal_time_off_lines_allocation = self.time_off_line_ids.filtered(
            lambda t: t.year == current_year.year and t.leave_type_id.id in legal_time_off_types
        )
        legal_time_off_lines_leave = self.time_off_line_ids.filtered(
            lambda t: t.year == current_year.year and t.leave_type_id.id in legal_time_off_types
        )
        time_off_allocated = legal_time_off_lines_allocation.leave_allocation_count
        time_off_taken = legal_time_off_lines_leave.leave_count
        european_wds = payslip_n1.mapped('worked_days_line_ids').filtered(lambda wd: wd.code == 'LEAVE216')
        european_leaves_amount = sum(european_wds.mapped('amount'))
        european_leaves_days = sum(european_wds.mapped('number_of_days'))
        european_amount_to_deduct = max(european_leaves_amount - double_amount_n, 0)

        self.env['hr.payslip.input'].create([{
            'payslip_id': termination_payslip_n1.id,
            'sequence': 1,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_gross_ref').id,
            'amount': self.gross_reference_remuneration_n1,
            'version_id': termination_payslip_n1.version_id.id
        }, {
            'payslip_id': termination_payslip_n1.id,
            'sequence': 3,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_allocation').id,
            'amount': time_off_allocated,
            'version_id': termination_payslip_n1.version_id.id
        }, {
            'payslip_id': termination_payslip_n1.id,
            'sequence': 4,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_time_off_taken').id,
            'amount': time_off_taken,
            'version_id': termination_payslip_n1.version_id.id
        }, {
            'payslip_id': termination_payslip_n1.id,
            'sequence': 5,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_annual_taxable_amount').id,
            'amount': annual_gross,
            'version_id': termination_payslip_n1.version_id.id
        }, {
            'payslip_id': termination_payslip_n1.id,
            'sequence': 6,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_european_leave').id,
            'amount': european_amount_to_deduct,
            'version_id': termination_payslip_n1.version_id.id
        }, {
            'payslip_id': termination_payslip_n1.id,
            'sequence': 7,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_european_leave_days').id,
            'amount': european_leaves_days,
            'version_id': termination_payslip_n1.version_id.id
        }])
        termination_payslip_n1.compute_sheet()
        termination_payslip_n1.name = '%s - %s' % (struct_n1_id.payslip_name, self.employee_id.legal_name)

        return {
            'name': _('Termination'),
            'domain': [('id', 'in', [termination_payslip_n.id, termination_payslip_n1.id])],
            'res_model': 'hr.payslip',
            'view_id': False,
            'view_mode': 'list,form',
            'type': 'ir.actions.act_window',
        }


class HrPayslipEmployeeDepatureHolidayAttestsTimeOffLine(models.TransientModel):
    _name = 'hr.payslip.employee.depature.holiday.attests.time.off.line'
    _description = 'Holiday Attest Time Off Line'

    wizard_id = fields.Many2one('hr.payslip.employee.depature.holiday.attests')
    year = fields.Integer()
    leave_type_id = fields.Many2one('hr.leave.type', string='Time Off Type')
    leave_allocation_count = fields.Integer(string='Allocations')
    leave_count = fields.Integer(string="Leaves")
