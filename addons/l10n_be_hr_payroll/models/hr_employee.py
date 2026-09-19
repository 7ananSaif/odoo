# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import date
from dateutil.relativedelta import relativedelta
from functools import reduce

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_round


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    niss = fields.Char(
        'NISS Number', compute="_compute_niss", store=True, readonly=False,
        groups="hr.group_hr_user", tracking=True, index=True)
    spouse_fiscal_status_explanation = fields.Char(compute='_compute_spouse_fiscal_status_explanation', groups="hr.group_hr_user")

    start_notice_period = fields.Date("Start notice period", groups="hr.group_hr_user", copy=False, tracking=True)
    end_notice_period = fields.Date("End notice period", groups="hr.group_hr_user", copy=False, tracking=True)
    first_contract_in_company = fields.Date("First contract in company", groups="hr.group_hr_user", copy=False)

    l10n_be_scale_seniority = fields.Integer(string="Seniority at Hiring", groups="hr.group_hr_user", tracking=True)

    # The attestation for the year of the first contract date
    first_contract_year_n = fields.Char(compute='_compute_first_contract_year', groups="hr_payroll.group_hr_payroll_user")
    first_contract_year_n_plus_1 = fields.Char(compute='_compute_first_contract_year', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_holiday_pay_to_recover_n = fields.Float(
        string="Simple Holiday Pay to Recover (N)", tracking=True, groups="hr_payroll.group_hr_payroll_user",
        help="Amount of the holiday pay paid by the previous employer to recover.")
    l10n_be_holiday_pay_number_of_days_n = fields.Float(
        string="Number of days to recover (N)", tracking=True, groups="hr_payroll.group_hr_payroll_user",
        help="Number of days on which you should recover the holiday pay.")
    l10n_be_holiday_pay_recovered_n = fields.Float(
        string="Recovered Simple Holiday Pay (N)", tracking=True,
        compute='_compute_l10n_be_holiday_pay_recovered', groups="hr_payroll.group_hr_payroll_user",
        help="Amount of the holiday pay paid by the previous employer already recovered.")
    double_pay_line_n_ids = fields.Many2many(
        'l10n.be.double.pay.recovery.line', 'double_pay_n_rel' 'employee_id', 'double_pay_line_n_ids',
        compute='_compute_from_double_pay_line_ids', readonly=False,
        inverse='_inverse_double_pay_line_n_ids',
        string='Previous Occupations (N)', groups="hr_payroll.group_hr_payroll_user")

    # The attestation for the previous year of the first contract date
    first_contract_year_n1 = fields.Char(compute='_compute_first_contract_year', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_holiday_pay_to_recover_n1 = fields.Float(
        string="Simple Holiday Pay to Recover (N-1)", tracking=True, groups="hr_payroll.group_hr_payroll_user",
        help="Amount of the holiday pay paid by the previous employer to recover.")
    l10n_be_holiday_pay_number_of_days_n1 = fields.Float(
        string="Number of days to recover (N-1)", tracking=True, groups="hr_payroll.group_hr_payroll_user",
        help="Number of days on which you should recover the holiday pay.")
    l10n_be_holiday_pay_recovered_n1 = fields.Float(
        string="Recovered Simple Holiday Pay (N-1)", tracking=True,
        compute='_compute_l10n_be_holiday_pay_recovered', groups="hr_payroll.group_hr_payroll_user",
        help="Amount of the holiday pay paid by the previous employer already recovered.")
    double_pay_line_n1_ids = fields.Many2many(
        'l10n.be.double.pay.recovery.line', 'double_pay_n1_rel' 'employee_id', 'double_pay_line_n1_ids',
        compute='_compute_from_double_pay_line_ids', readonly=False,
        inverse='_inverse_double_pay_line_n1_ids',
        string='Previous Occupations (N-1)', groups="hr_payroll.group_hr_payroll_user")
    first_contract_year = fields.Integer(compute='_compute_first_contract_year', groups="hr_payroll.group_hr_payroll_user")
    double_pay_line_ids = fields.One2many(
        'l10n.be.double.pay.recovery.line', 'employee_id',
        string='Previous Occupations', groups="hr_payroll.group_hr_payroll_user")

    fiscal_voluntarism = fields.Monetary(readonly=False, related="version_id.fiscal_voluntarism", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    transport_mode_car = fields.Boolean(readonly=False, related="version_id.transport_mode_car", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    transport_mode_private_car = fields.Boolean(readonly=False, related="version_id.transport_mode_private_car", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    transport_mode_train = fields.Boolean(readonly=False, related="version_id.transport_mode_train", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    transport_mode_public = fields.Boolean(readonly=False, related="version_id.transport_mode_public", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    car_atn = fields.Monetary(readonly=False, related="version_id.car_atn", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    train_transport_employee_amount = fields.Monetary(readonly=False, related="version_id.train_transport_employee_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    public_transport_employee_amount = fields.Monetary(readonly=False, related="version_id.public_transport_employee_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    warrant_value_employee = fields.Monetary(related="version_id.warrant_value_employee", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_paid_by_employer = fields.Monetary(related="version_id.meal_voucher_paid_by_employer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_paid_monthly_by_employer = fields.Monetary(related="version_id.meal_voucher_paid_monthly_by_employer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    company_car_total_depreciated_cost = fields.Monetary(readonly=False, related="version_id.company_car_total_depreciated_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    private_car_reimbursed_amount = fields.Monetary(related="version_id.private_car_reimbursed_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    train_transport_reimbursed_amount = fields.Monetary(readonly=False, related="version_id.train_transport_reimbursed_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    public_transport_reimbursed_amount = fields.Monetary(readonly=False, related="version_id.public_transport_reimbursed_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    warrants_cost = fields.Monetary(related="version_id.warrants_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    yearly_commission = fields.Monetary(related="version_id.yearly_commission", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    yearly_commission_cost = fields.Monetary(related="version_id.yearly_commission_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    commission_on_target = fields.Monetary(readonly=False, related="version_id.commission_on_target", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    fuel_card = fields.Monetary(readonly=False, related="version_id.fuel_card", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    internet = fields.Monetary(readonly=False, related="version_id.internet", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    representation_fees = fields.Monetary(readonly=False, related="version_id.representation_fees", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    mobile = fields.Monetary(readonly=False, related="version_id.mobile", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    has_laptop = fields.Boolean(readonly=False, related="version_id.has_laptop", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_amount = fields.Monetary(readonly=False, related="version_id.meal_voucher_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_average_monthly_amount = fields.Monetary(related="version_id.meal_voucher_average_monthly_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    eco_checks = fields.Monetary(readonly=False, related="version_id.eco_checks", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    ip = fields.Boolean(readonly=False, related="version_id.ip", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    ip_wage_rate = fields.Float(readonly=False, related="version_id.ip_wage_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    ip_value = fields.Float(related="version_id.ip_value", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    no_onss = fields.Boolean(readonly=False, related="version_id.no_onss", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    no_withholding_taxes = fields.Boolean(readonly=False, related="version_id.no_withholding_taxes", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    rd_percentage = fields.Integer(readonly=False, related="version_id.rd_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_impulsion_plan = fields.Selection(readonly=False, related="version_id.l10n_be_impulsion_plan", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_onss_restructuring = fields.Boolean(readonly=False, related="version_id.l10n_be_onss_restructuring", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    has_hospital_insurance = fields.Boolean(readonly=False, related="version_id.has_hospital_insurance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    insured_relative_children = fields.Integer(readonly=False, related="version_id.insured_relative_children", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    insured_relative_adults = fields.Integer(readonly=False, related="version_id.insured_relative_adults", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    insured_relative_spouse = fields.Boolean(readonly=False, related="version_id.insured_relative_spouse", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    hospital_insurance_amount_per_child = fields.Float(readonly=False, related="version_id.hospital_insurance_amount_per_child", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    hospital_insurance_amount_per_adult = fields.Float(readonly=False, related="version_id.hospital_insurance_amount_per_adult", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    insurance_amount = fields.Float(related="version_id.insurance_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    insured_relative_adults_total = fields.Integer(related="version_id.insured_relative_adults_total", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_hospital_insurance_notes = fields.Text(readonly=False, related="version_id.l10n_be_hospital_insurance_notes", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    wage_with_holidays = fields.Monetary(readonly=False, related="version_id.wage_with_holidays", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    # Group Insurance
    l10n_be_group_insurance_rate = fields.Float(readonly=False, related="version_id.l10n_be_group_insurance_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_amount = fields.Monetary(related="version_id.l10n_be_group_insurance_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_cost = fields.Monetary(related="version_id.l10n_be_group_insurance_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    # Ambulatory Insurance
    l10n_be_has_ambulatory_insurance = fields.Boolean(readonly=False, related="version_id.l10n_be_has_ambulatory_insurance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insured_children = fields.Integer(readonly=False, related="version_id.l10n_be_ambulatory_insured_children", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insured_adults = fields.Integer(readonly=False, related="version_id.l10n_be_ambulatory_insured_adults", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insured_spouse = fields.Boolean(readonly=False, related="version_id.l10n_be_ambulatory_insured_spouse", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_amount_per_child = fields.Float(readonly=False, related="version_id.l10n_be_ambulatory_amount_per_child", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_amount_per_adult = fields.Float(readonly=False, related="version_id.l10n_be_ambulatory_amount_per_adult", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insurance_amount = fields.Float(related="version_id.l10n_be_ambulatory_insurance_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insured_adults_total = fields.Integer(related="version_id.l10n_be_ambulatory_insured_adults_total", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insurance_notes = fields.Text(readonly=False, related="version_id.l10n_be_ambulatory_insurance_notes", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    l10n_be_mobility_budget = fields.Boolean(readonly=False, related="version_id.l10n_be_mobility_budget", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_mobility_budget_amount = fields.Monetary(readonly=False, related="version_id.l10n_be_mobility_budget_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_mobility_budget_amount_monthly = fields.Monetary(related="version_id.l10n_be_mobility_budget_amount_monthly", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_wage_with_mobility_budget = fields.Monetary(readonly=False, related="version_id.l10n_be_wage_with_mobility_budget", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    l10n_be_is_below_scale_warning = fields.Char(readonly=False, related="version_id.l10n_be_is_below_scale_warning", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_canteen_cost = fields.Monetary(readonly=False, related="version_id.l10n_be_canteen_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    def _get_certificate_selection(self):
        if self.env.company.country_id.code != "BE":
            return super()._get_certificate_selection()
        certificate_selection = [
            ('primary', self.env._('Primary School')),
            ('lower_secondary', self.env._('Lower Secondary')),
            ('higher_secondary', self.env._('Higher Secondary'))
        ]
        civil_engineer_added = False
        for selection in super()._get_certificate_selection():
            certificate_selection += [selection]
            if selection[0] == 'master':
                certificate_selection += [('civil_engineer', self.env._('Master: Civil Engineering'))]
                civil_engineer_added = True
        if not civil_engineer_added:
            certificate_selection += [('civil_engineer', self.env._('Master: Civil Engineering'))]
        return certificate_selection

    @api.depends('version_ids.date_version', 'version_ids.contract_date_start', 'version_ids.contract_date_end')
    def _compute_first_contract_year(self):
        for employee in self:
            version_date = employee._get_first_version_date()
            year = (version_date or fields.Date.today()).year
            employee.first_contract_year = year
            employee.first_contract_year_n = year
            employee.first_contract_year_n1 = year - 1
            employee.first_contract_year_n_plus_1 = year + 1

    def _compute_from_double_pay_line_ids(self):
        for employee in self:
            year = employee.first_contract_year
            employee.double_pay_line_n_ids = employee.double_pay_line_ids.filtered(lambda d: d.year == year)
            employee.double_pay_line_n1_ids = employee.double_pay_line_ids.filtered(lambda d: d.year == year - 1)

    def _inverse_double_pay_line_n_ids(self):
        for employee in self:
            year = employee.first_contract_year
            to_be_deleted = employee.double_pay_line_ids.filtered(lambda d: d.year == year) - employee.double_pay_line_n_ids
            employee.double_pay_line_ids.filtered(lambda d: d.id in to_be_deleted.ids).unlink()
            employee.double_pay_line_ids |= employee.double_pay_line_n_ids

    def _inverse_double_pay_line_n1_ids(self):
        for employee in self:
            year = employee.first_contract_year
            to_be_deleted = employee.double_pay_line_ids.filtered(lambda d: d.year == year - 1) - employee.double_pay_line_n1_ids
            employee.double_pay_line_ids.filtered(lambda d: d.id in to_be_deleted.ids).unlink()
            employee.double_pay_line_ids |= employee.double_pay_line_n1_ids

    @api.constrains('start_notice_period', 'end_notice_period')
    def _check_notice_period(self):
        for employee in self:
            if employee.start_notice_period and employee.end_notice_period and employee.start_notice_period > employee.end_notice_period:
                raise ValidationError(_('The employee start notice period should be set before the end notice period'))

    def _compute_l10n_be_holiday_pay_recovered(self):
        payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', self.ids),
            ('struct_id', '=', self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id),
            ('company_id', '=', self.env.company.id),
            ('state', 'in', ['validated', 'paid']),
        ])
        line_values = payslips._get_line_values(['HolPayRecN', 'HolPayRecN1'])
        payslips_by_employee = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in payslips:
            payslips_by_employee[payslip.employee_id] |= payslip

        for employee in self:
            employee_payslips = payslips_by_employee[employee]
            employee.l10n_be_holiday_pay_recovered_n = - sum(line_values['HolPayRecN'][p.id]['total'] for p in employee_payslips)
            employee.l10n_be_holiday_pay_recovered_n1 = - sum(line_values['HolPayRecN1'][p.id]['total'] for p in employee_payslips)

    def _compute_spouse_fiscal_status_explanation(self):
        no_income_threshold = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('spouse_no_income_threshold')
        low_income_threshold = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('spouse_low_income_threshold')
        other_income_threshold = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('spouse_other_income_threshold')
        for employee in self:
            employee.spouse_fiscal_status_explanation = _("""- High Income: Spouse earns more than %(low_income_threshold)s€ net/month.\n
- Low Income: Spouse earns between %(no_income_threshold)s€ and %(low_income_threshold)s€ net/month.\n
- Without Income: Spouse earns less than %(no_income_threshold)s€ net/month.\n
- High Pensions : Spouse is eligible to a pension higher than %(other_income_threshold)s€ net/month.\n
- Low Pensions : Spouse is eligible to a pension lower than %(other_income_threshold)s€ net/month.\n
Earnings are made of professional income, remuneration, unemployment allocations, annuities or similar income.""",
        no_income_threshold=no_income_threshold,
        low_income_threshold=low_income_threshold,
        other_income_threshold=other_income_threshold)

    @api.depends('identification_id')
    def _compute_niss(self):
        characters = dict.fromkeys([',', '.', '-', ' '], '')
        for employee in self:
            if employee.identification_id and not employee.niss and employee.company_country_code == 'BE':
                employee.niss = reduce(lambda a, kv: a.replace(*kv), characters.items(), employee.identification_id)

    @api.model
    def _validate_niss(self, niss):
        try:
            test = niss[:-2]
            if test[0] in ['0', '1', '2', '3', '4', '5']:  # Should be good for several years
                test = '2%s' % test
            checksum = int(niss[-2:])
            if checksum != (97 - int(test) % 97):
                raise Exception()
            return True
        except Exception:
            return False

    def _is_niss_valid(self):
        # The last 2 positions constitute the check digit. This check digit is
        # a sequence of 2 digits forming a number between 01 and 97. This number is equal to 97
        # minus the remainder of the division by 97 of the number formed:
        # - either by the first 9 digits of the national number for people born before the 1st
        # January 2000.
        # - either by the number 2 followed by the first 9 digits of the national number for people
        # born after December 31, 1999.
        # (https://fr.wikipedia.org/wiki/Num%C3%A9ro_de_registre_national)
        self.ensure_one()
        niss = self.niss
        if not niss or len(niss) != 11:
            return False
        return self._validate_niss(niss)

    @api.onchange('disabled_children_bool')
    def _onchange_disabled_children_bool(self):
        self.disabled_children_number = 0

    @api.onchange('other_dependent_people')
    def _onchange_other_dependent_people(self):
        self.other_senior_dependent = 0.0
        self.other_disabled_senior_dependent = 0.0
        self.other_juniors_dependent = 0.0
        self.other_disabled_juniors_dependent = 0.0

    @api.onchange('has_hospital_insurance')
    def _onchange_has_hospital_insurance(self):
        self.version_id._onchange_has_hospital_insurance()

    @api.onchange('l10n_be_has_ambulatory_insurance')
    def _onchange_l10n_be_has_ambulatory_insurance(self):
        self.version_id._onchange_l10n_be_has_ambulatory_insurance()

    @api.onchange('transport_mode_car', 'transport_mode_train', 'transport_mode_public')
    def _onchange_transport_mode(self):
        self.version_id._onchange_transport_mode()

    @api.onchange('transport_mode_private_car')
    def _onchange_transport_mode_private_car(self):
        self.version_id._onchange_transport_mode_private_car()

    @api.model
    def _get_invalid_niss_employee_ids(self):
        res = self.search_read([
            ('company_id', 'in', self.env.companies.filtered(lambda c: c.country_id.code == 'BE').ids),
            ('employee_type', 'in', ('employee', 'student')),
        ], ['id', 'niss'])
        return [row['id'] for row in res if not row['niss'] or not self._validate_niss(row['niss'])]

    def _get_first_versions(self):
        self.ensure_one()
        versions = super()._get_first_versions()
        pfi = self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_pfi', raise_if_not_found=False)
        if not pfi:
            return versions
        return versions.filtered(
            lambda c: c.company_id.country_id.code != 'BE' or (c.company_id.country_id.code == 'BE' and c.contract_type_id != pfi))

    def write(self, vals):
        res = super().write(vals)
        if vals.get('current_version_id'):
            self.current_version_id.sudo().filtered('contract_date_start')._trigger_l10n_be_next_activities()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees.current_version_id.sudo().filtered('contract_date_start')._trigger_l10n_be_next_activities()
        return employees

    def action_employee_work_schedule_change_wizard(self):
        if len(self) != 1:
            raise UserError(self.env._("This feature can only be used on a single employee."))
        if not self.contract_date_start:
            raise UserError(self.env._('This feature can only be used on versions that have a contract start date'))
        action = self.env['ir.actions.actions']._for_xml_id('l10n_be_hr_payroll.schedule_change_wizard_action')
        action['context'] = {'default_version_id': self.current_version_id.id}
        return action

    def action_open_attest_wizard(self):
        self.ensure_one()

        default_year = self.env.context.get('default_year')
        default_employee_id = self.id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Attestation Line',
            'res_model': 'l10n.be.holiday.attest.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_year': default_year,
                'default_employee_id': default_employee_id,
            }
        }

    # --- Holiday Attest Helper Methods --- #

    @api.model
    def _get_l10n_be_holiday_attest_non_equivalent_codes(self):
        # In french non-equivalent means "Non-assimilés"
        return [
            'LEAVE90',   # Unpaid
            'LEAVE700',  # Unjustified reason
            'LEAVE250',  # Unpredictable reason
            'LEAVE300',  # Credit Time
        ]

    def _get_l10n_be_holiday_attest_worked_days(self, date_from, date_to):
        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', 'in', ['validated', 'paid'])
        ])
        all_days = sum(payslips.worked_days_line_ids.mapped('number_of_days'))
        non_equivalent_days = sum(
            payslips.worked_days_line_ids.filtered(
                lambda wd: wd.code in self._get_l10n_be_holiday_attest_non_equivalent_codes()
            ).mapped('number_of_days')
        )
        equivalent_days = all_days - non_equivalent_days
        return equivalent_days, non_equivalent_days

    def get_l10n_be_holiday_attest_occupations(self, year):
        first_of_year = date(year, 1, 1)
        last_of_year = min(date(year, 12, 31), self.end_notice_period or self.departure_date or date.today())
        versions = self.version_ids.filtered(
            lambda v: v._is_overlapping_period(first_of_year, last_of_year)
        )
        if not versions:
            return []
        occupations = []
        for idx, version in enumerate(versions):
            previous_occupation_work_time_rate = (
                float_round(versions[idx - 1].hours_per_week, 2), versions[idx - 1].resource_calendar_id._get_days_per_week()
            ) if idx != 0 else None
            occupation_work_time_rate = (
                float_round(version.hours_per_week, 2), version.resource_calendar_id._get_days_per_week()
            )
            if previous_occupation_work_time_rate != occupation_work_time_rate:
                if occupations:
                    equivalent_days, non_equivalent_days = self._get_l10n_be_holiday_attest_worked_days(
                        occupations[-1]['date_start'], version.date_version - relativedelta(days=1)
                    )
                    occupations[-1].update({
                        'date_end': version.date_version - relativedelta(days=1),
                        'equivalent_days': equivalent_days,
                        'non_equivalent_days': non_equivalent_days
                    })
                occupations.append({
                    'date_start': max(first_of_year, version.date_version),
                    'hours_per_week': float_round(version.hours_per_week, 2),
                    'days_per_week': version.resource_calendar_id._get_days_per_week(),
                })
        equivalent_days, non_equivalent_days = self._get_l10n_be_holiday_attest_worked_days(
            occupations[-1]['date_start'], last_of_year
        )
        occupations[-1].update({
            'date_end': last_of_year,
            'equivalent_days': equivalent_days,
            'non_equivalent_days': non_equivalent_days
        })
        return occupations
