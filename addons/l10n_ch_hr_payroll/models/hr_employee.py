# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

import re


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_ch_sv_as_number = fields.Char(
        string="Social Insurance N°",
        groups="hr.group_hr_user",
        help="Thirteen-digit AS number assigned by the Central Compensation Office (CdC)", tracking=True)

    l10n_ch_children = fields.One2many('l10n.ch.hr.employee.children', 'employee_id', groups="hr_payroll.group_hr_payroll_user")
    certificate = fields.Selection(ondelete={
        'universityBachelor': 'set default',
        'universityMaster': 'set default',
        'higherEducationMaster': 'set default',
        'higherEducationBachelor': 'set default',
        'higherVocEducation': 'set default',
        'higherVocEducationMaster': 'set default',
        'higherVocEducationBachelor': 'set default',
        'teacherCertificate': 'set default',
        'universityEntranceCertificate': 'set default',
        'vocEducationCompl': 'set default',
        'enterpriseEducation': 'set default',
        'mandatorySchoolOnly': 'set default',
        'doctorate': 'set default'
    }, default='mandatorySchoolOnly')

    l10n_ch_legal_first_name = fields.Char(string="First Name", compute="_compute_l10n_ch_legal_name", store=True, readonly=False, tracking=True, groups="hr.group_hr_user")
    l10n_ch_legal_last_name = fields.Char(string="Last Name", compute="_compute_l10n_ch_legal_name", store=True, readonly=False, tracking=True, groups="hr.group_hr_user")
    l10n_ch_is_mutations = fields.One2many('l10n.ch.is.mutation', 'employee_id', groups="hr.group_hr_user")
    l10n_ch_salary_certificate_profiles = fields.One2many("l10n.ch.salary.certificate.profile", "employee_id", groups="hr.group_hr_user")

    l10n_ch_tax_scale_type = fields.Selection(readonly=False, related="version_id.l10n_ch_tax_scale_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_pre_defined_tax_scale = fields.Selection(readonly=False, related="version_id.l10n_ch_pre_defined_tax_scale", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_open_tax_scale = fields.Char(readonly=False, related="version_id.l10n_ch_open_tax_scale", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_tax_specially_approved = fields.Boolean(readonly=False, related="version_id.l10n_ch_tax_specially_approved", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_tax_code = fields.Char(readonly=True, related="version_id.l10n_ch_tax_code", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_source_tax_canton = fields.Char(readonly=True, related="version_id.l10n_ch_source_tax_canton", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_source_tax_municipality = fields.Char(readonly=True, related="version_id.l10n_ch_source_tax_municipality", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_other_employment = fields.Boolean(readonly=False, related="version_id.l10n_ch_other_employment", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_total_activity_type = fields.Selection(readonly=False, related="version_id.l10n_ch_total_activity_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_other_activity_percentage = fields.Float(readonly=False, related="version_id.l10n_ch_other_activity_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_other_activity_gross = fields.Float(readonly=False, related="version_id.l10n_ch_other_activity_gross", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_tax_scale = fields.Selection(readonly=False, related="version_id.l10n_ch_tax_scale", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_religious_denomination = fields.Selection(readonly=False, related="version_id.l10n_ch_religious_denomination", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_church_tax = fields.Boolean(readonly=False, related="version_id.l10n_ch_church_tax", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    irregular_working_time = fields.Boolean(readonly=False, related="version_id.irregular_working_time", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_weekly_hours = fields.Float(readonly=False, related="version_id.l10n_ch_weekly_hours", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_thirteen_month = fields.Boolean(readonly=False, related="version_id.l10n_ch_thirteen_month", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_lesson_wage = fields.Float(readonly=False, related="version_id.l10n_ch_lesson_wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_contractual_13th_month_rate = fields.Float(readonly=False, related="version_id.l10n_ch_contractual_13th_month_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_location_unit_id = fields.Many2one(readonly=False, related="version_id.l10n_ch_location_unit_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_current_occupation_rate = fields.Float(readonly=False, related="version_id.l10n_ch_current_occupation_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_other_employers_occupation_rate = fields.Float(readonly=True, related="version_id.l10n_ch_other_employers_occupation_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_total_occupation_rate = fields.Float(readonly=True, related="version_id.l10n_ch_total_occupation_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_contractual_holidays_rate = fields.Float(readonly=False, related="version_id.l10n_ch_contractual_holidays_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_contractual_public_holidays_rate = fields.Float(readonly=False, related="version_id.l10n_ch_contractual_public_holidays_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_contractual_vacation_pay = fields.Boolean(readonly=False, related="version_id.l10n_ch_contractual_vacation_pay", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_contractual_annual_wage = fields.Monetary(readonly=False, related="version_id.l10n_ch_contractual_annual_wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_contract_wage_ids = fields.One2many(readonly=False, related="version_id.l10n_ch_contract_wage_ids", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    one_time_wage_count = fields.Integer(readonly=True, related="version_id.one_time_wage_count", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_has_monthly = fields.Boolean(readonly=False, related="version_id.l10n_ch_has_monthly", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_has_hourly = fields.Boolean(readonly=False, related="version_id.l10n_ch_has_hourly", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_has_lesson = fields.Boolean(readonly=False, related="version_id.l10n_ch_has_lesson", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    @api.constrains('birthday')
    def _check_birthday(self):
        today = fields.Datetime.now().date()
        for employee in self:
            if employee.birthday and employee.birthday > today:
                raise ValidationError(_("Employee's Birthday cannot be greater than today."))

    @api.onchange('private_country_id')
    def _onchange_private_country_id(self):
        self.version_id._onchange_private_country_id()

    @api.onchange('l10n_ch_has_monthly')
    def _onchange_l10n_ch_has_monthly(self):
        self.version_id._onchange_l10n_ch_has_monthly()

    @api.onchange('l10n_ch_has_hourly')
    def _onchange_l10n_ch_has_hourly(self):
        self.version_id._onchange_l10n_ch_has_hourly()

    @api.onchange('l10n_ch_has_lesson')
    def _onchange_l10n_ch_has_lesson(self):
        self.version_id._onchange_l10n_ch_has_lesson()

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._create_or_update_snapshot()
        return employees

    def write(self, vals):
        vals = super().write(vals)
        self._create_or_update_snapshot()
        return vals

    def _get_certificate_selection(self):
        if self.env.company.country_id.code != "CH":
            return super()._get_certificate_selection()
        return super()._get_certificate_selection() + [
            ('universityBachelor', self.env._('Swiss: University College Bachelor (university, ETH)')),
            ('universityMaster', self.env._('Swiss: University College Master (university, ETH)')),
            ('higherEducationMaster', self.env._('Swiss: University of Applied Sciences Master')),
            ('higherEducationBachelor', self.env._('Swiss: University of Applied Sciences Bachelor')),
            ('higherVocEducation', self.env._('Swiss: Higher Vocational Education')),
            ('higherVocEducationMaster', self.env._('Swiss: Higher Vocational Education Master')),
            ('higherVocEducationBachelor', self.env._('Swiss: Higher Vocational Education Bachelor')),
            ('teacherCertificate', self.env._('Swiss: Teaching certificate at different levels')),
            ('universityEntranceCertificate', self.env._('Swiss: Matura')),
            ('vocEducationCompl', self.env._('Swiss: Complete learning attested by a federal certificate of capacity (CFC)')),
            ('enterpriseEducation', self.env._('Swiss: In-company training only')),
            ('mandatorySchoolOnly', self.env._('Swiss: Compulsory schooling, without full vocational training')),
            ('doctorate', self.env._('Swiss: Doctorate, habilitation')),
        ]

    @api.depends("name")
    def _compute_l10n_ch_legal_name(self):
        for employee in self:
            if employee.name:
                first_name = ' '.join(re.sub(r"\([^()]*\)", "", employee.name).strip().split()[:-1])
                last_name = re.sub(r"\([^()]*\)", "", employee.name).strip().split()[-1]
                if not employee.l10n_ch_legal_last_name:
                    employee.l10n_ch_legal_last_name = first_name
                if not employee.l10n_ch_legal_first_name:
                    employee.l10n_ch_legal_first_name = last_name

    @api.model
    def _create_or_update_snapshot(self):

        swiss_employees = self.filtered(lambda e: e.company_id.country_id.code == "CH")
        if not swiss_employees:
            return

        self.env.flush_all()
        now = fields.Datetime.now().date()
        month = now.month
        year = now.year
        existing_snapshots = self.sudo().env["l10n.ch.employee.yearly.values"].search([
            ('year', '=', year),
            ('employee_id', 'in', swiss_employees.ids)
        ])
        snapshots_to_update = existing_snapshots.mapped('employee_id')
        snapshots_to_create = swiss_employees - snapshots_to_update
        vals = []
        for employee in snapshots_to_create:
            vals.append({
                'employee_id': employee.id,
                'year': year
            })

        if vals:
            existing_snapshots += self.sudo().env['l10n.ch.employee.yearly.values'].create(vals)

        existing_snapshots += self.sudo().env["l10n.ch.employee.yearly.values"].search([
            ('year', '>', year),
            ('employee_id', 'in', self.ids)
        ])

        # Mutation insensitive informations, these have to be updated even if the payroll month is closed
        monthly_persons_to_update = existing_snapshots.monthly_value_ids.filtered(lambda s: not s.payroll_month_closed or (s.month >= month and s.year >= year)).sorted(lambda s: (s.year, s.month))
        self.env.add_to_compute(self.env['l10n.ch.employee.monthly.values']._fields['person'], monthly_persons_to_update)
        monthly_persons_to_update._recompute_recordset(['person'])

        # Mutation sensitive informations, these should not be recomputed once payroll month is closed
        monthly_values_to_update = existing_snapshots.monthly_value_ids.filtered(lambda s: not s.payroll_month_closed).sorted(lambda s: (s.year, s.month))

        if self.env.context.get('update_salaries'):
            self.env.add_to_compute(self.env['l10n.ch.employee.monthly.values']._fields['bvg_lpp_annual_basis'], monthly_values_to_update)
            monthly_values_to_update._recompute_recordset(['bvg_lpp_annual_basis'])

        self.env.add_to_compute(self.env['l10n.ch.employee.monthly.values']._fields['employee_meta_data'], monthly_values_to_update)
        self.env.add_to_compute(self.env['l10n.ch.employee.monthly.values']._fields['additional_particular'], monthly_values_to_update)
        monthly_values_to_update._recompute_recordset(['employee_meta_data', 'additional_particular'])

        self.env.add_to_compute(self.env['l10n.ch.employee.monthly.values']._fields['lpp_mutations'], monthly_values_to_update)
        self.env.add_to_compute(self.env['l10n.ch.employee.monthly.values']._fields['is_mutations'], monthly_values_to_update)
        monthly_values_to_update._recompute_recordset(['lpp_mutations', 'is_mutations'])

        self.env.add_to_compute(self.env['l10n.ch.employee.monthly.values']._fields['monthly_statistics'], monthly_values_to_update)
        monthly_values_to_update._recompute_recordset(['monthly_statistics'])

        if self.env.context.get('lock_pay_period'):
            existing_snapshots._toggle_pay_period_lock(lock=True)

        if self.env.context.get('unlock_pay_period'):
            existing_snapshots._toggle_pay_period_lock(lock=False)

        # Recompute open payslips automatically on each update since almost all fields cause a change in computation
        pending_computation_slips = self.sudo().slip_ids.filtered(lambda p: p.state == 'draft' and p.struct_id.code == "CHMONTHLYELM")
        if pending_computation_slips:
            pending_computation_slips.action_refresh_from_work_entries()

    def action_absence_swiss_employee(self):
        return {
            'name': _('Absences'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave',
            'views': [[self.env.ref('l10n_ch_hr_payroll.l10n_ch_hr_leave_employee_view_dashboard').id, 'calendar']],
            'domain': [('employee_id', 'in', self.ids)],
            'context': {
                'employee_id': self.ids,
            },
        }

    def action_view_wages(self):
        self.ensure_one()
        if self.version_id:
            return self.version_id.action_view_wages()
        else:
            raise UserError(_("Oops, this employee has no contract yet."))

    @api.model
    def _validate_sv_as_number(self, sv_as_number):
        pattern = r"^\d{3}\.\d{4}\.\d{4}\.\d{2}$"
        if not re.match(pattern, sv_as_number):
            raise UserError(
                _('The SV-AS number should be a thirteen-digit number, dot-separated (eg: 756.1848.4786.64)'))

        sv_as_number = sv_as_number.replace('.', '')
        first_12_digits = sv_as_number[:12]
        weights = [1, 3] * 6  # Alternating pattern
        weighted_sum = sum(int(digit) * weight for digit, weight in zip(first_12_digits, weights))
        nearest_multiple_of_10 = (weighted_sum + 9) // 10 * 10
        check_digit = nearest_multiple_of_10 - weighted_sum

        # Compare with the 13th digit of the number
        if check_digit != int(sv_as_number[-1]):
            raise UserError(
                _('Incorrect EAN13 Check-sum for this SV-AS Number'))

    @api.constrains('l10n_ch_sv_as_number')
    def _check_l10n_ch_sv_as_number(self):
        """
        SV-AS number is encoded using EAN13 Standard Checksum control
        """
        for employee in self:
            if not employee.l10n_ch_sv_as_number:
                continue
            self._validate_sv_as_number(employee.l10n_ch_sv_as_number)
