from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_amount


class HrVersion(models.Model):
    """
    Employee contract allows to add different values in fields.
    Fields are used in salary rule computation.
    """
    _inherit = 'hr.version'

    def _l10n_in_get_pf_selection(self):
        rule_parameter = self.env['hr.rule.parameter']
        pf_amount = rule_parameter._get_parameter_from_code('l10n_in_pf_amount', raise_if_not_found=False) or 0
        pf_percentage = rule_parameter._get_parameter_from_code('l10n_in_pf_percent', raise_if_not_found=False) or 0
        pf_format_amount = format_amount(self.env, pf_amount, self.env.company.currency_id)
        return [
            ('fixed', self.env._("Restrict contribution to %(amount)s of PF Wage", amount=pf_format_amount)),
            ('calculate', self.env._("%(percentage)s%% of actual PF wages", percentage=pf_percentage * 100))
        ]

    # ----- Allowances -----
    l10n_in_residing_child_hostel = fields.Integer("Child Residing in hostel", groups="hr_payroll.group_hr_payroll_user",
        tracking=True)
    l10n_in_hra_percentage = fields.Float(string="House Rent Allowance Percentage",
        compute="_compute_l10n_in_hra_percentage", store=True, readonly=False,
        help='House Rent Allowance computed as percentage(%)', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_in_hra = fields.Monetary(string="House Rent Allowance", compute="_compute_l10n_in_hra", store=True,
        groups="hr_payroll.group_hr_payroll_user", readonly=False, tracking=True,
        help='HRA allowance is provided to employees for rental and accommodation benefits 50% of the basic salary for\
        metro cities and 40% for non-metro cities.')
    l10n_in_leave_travel_percentage = fields.Float(string="Leave Travel Allowance Percentage",
        compute="_compute_l10n_in_leave_travel_percentage", store=True, readonly=False, tracking=True,
        groups="hr_payroll.group_hr_payroll_user", help='Percentage(%) to calculate leave travel allowance amount.')
    l10n_in_leave_travel_allowance = fields.Monetary(string='Leave Travel Allowance', tracking=True,
        compute="_compute_l10n_in_leave_travel_allowance", store=True, readonly=False,
        groups="hr_payroll.group_hr_payroll_user",
        help='LTA is paid by the company to employees to cover their travel expenses. LTA is defined by the company and\
        is calculated as a % of the basic salary.')
    l10n_in_basic_salary_amount = fields.Monetary(string="Basic Salary", compute="_compute_l10n_in_basic_salary_amount",
        readonly=False, store=True, groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help="Define Basic salary from company cost compute it based on Wages (Including DA)")
    l10n_in_basic_percentage = fields.Float(string="Basic Salary Percentage", groups="hr_payroll.group_hr_payroll_user",
        compute="_compute_l10n_in_basic_percentage", store=True, readonly=False, tracking=True)
    l10n_in_standard_allowance = fields.Monetary(string="Standard Allowance", tracking=True,
        compute="_compute_l10n_in_standard_allowance", store=True, readonly=False,
        groups="hr_payroll.group_hr_payroll_user",
        help='A standard allowance is a predetermined, fixed amount provided to employees as part of their salary\
        package, irrespective of actual expenses incurred')
    l10n_in_standard_allowance_percentage = fields.Float(string="Standard Allowance Percentage",
        compute="_compute_l10n_in_standard_allowance_percentage", store=True, readonly=False, tracking=True,
        groups="hr_payroll.group_hr_payroll_user", help='Standard Allowance computed as percentage(%)')
    l10n_in_performance_bonus_percentage = fields.Float(string="Performance Bonus Percentage",
        compute="_compute_l10n_in_performance_bonus_percentage", store=True, readonly=False, tracking=True,
        groups="hr_payroll.group_hr_payroll_user", help='Performance Bonus computed as percentage(%)')
    l10n_in_performance_bonus = fields.Monetary(string="Performance Bonus", compute="_compute_l10n_in_performance_bonus",
        store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help='Performance bonus is a variable amount given to employees. The value defined by the company and\
        calculated as a % of the basic salary')
    l10n_in_fixed_allowance_percentage = fields.Float(string='Fixed Allowance Percentage',
        compute="_compute_l10n_in_fixed_allowance_percentage", store=True, readonly=False, tracking=True,
        groups="hr_payroll.group_hr_payroll_user", help='Fixed Allowance computed as percentage(%)')
    l10n_in_fixed_allowance = fields.Monetary(string='Fixed Allowance', tracking=True,
        compute="_compute_l10n_in_fixed_allowance", store=True, groups="hr_payroll.group_hr_payroll_user", readonly=False,
        help='The remaining variable amount is computed as the fixed allowance after all other allowances defined.\
        this will represents the portion of wages remaining after the total of all other allowances.')
    l10n_in_phone_subscription = fields.Monetary(string="Phone Subscription", groups="hr_payroll.group_hr_payroll_user",
        tracking=True, help="Company may offer a phone subscription as a benefit which can be assigned to employees\
        during version generation.")
    l10n_in_internet_subscription = fields.Monetary(groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help="Company may offer a Internet subscription as a benefit which can be assigned to employees during version\
        generation.")
    l10n_in_meal_voucher_amount = fields.Monetary(groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help="Employees may receive meal vouchers as part of their compensation which can be assigned to employees\
        during 'version generation.")
    l10n_in_company_transport = fields.Monetary(string="Company Transport", groups="hr_payroll.group_hr_payroll_user",
        tracking=True, help="Company may offer transportation facilities to employees for daily commute.")
# ----- Deductions -----
    l10n_in_tds = fields.Float(string='TDS Deduction', digits='Payroll', groups="hr_payroll.group_hr_payroll_user",
        help='The TDS calculator can calculate the TDS amount when at least one payslip is available. Alternatively,\
        you can enter the amount manually')
    l10n_in_medical_insurance = fields.Monetary(string='Medical Insurance', tracking=True,
        groups="hr_payroll.group_hr_payroll_user",
        help='Employees can opt in for company-provided medical insurance. Coverage can be extended to their spouse\
        and children based on eligibility and policy.')
    l10n_in_insured_spouse = fields.Boolean(groups="hr_payroll.group_hr_payroll_user")
    l10n_in_insured_first_children = fields.Boolean(string="Insured First-Child", groups="hr_payroll.group_hr_payroll_user")
    l10n_in_insured_second_children = fields.Boolean(string="Insured Second-Child", groups="hr_payroll.group_hr_payroll_user")
    l10n_in_medical_insurance_total = fields.Monetary(string='Medical Insurance Amount', tracking=True,
        compute='_compute_l10n_in_medical_insurance_total', store=True, groups="hr_payroll.group_hr_payroll_user", readonly=False)
    pt_rule_parameter_id = fields.Many2one(
        'hr.rule.parameter',
        string='Professional Tax slab',
        help="Professional Tax rule parameter to be used for the company.",
        groups="hr_payroll.group_hr_payroll_user",
        domain="[('code', 'ilike', 'india_pt_')]"
    )
    l10n_in_pf_employer_type = fields.Selection(selection=_l10n_in_get_pf_selection, default='fixed',
        groups="hr_payroll.group_hr_payroll_user")
    l10n_in_pf_employee_type = fields.Selection(selection=_l10n_in_get_pf_selection, default='fixed',
        groups="hr_payroll.group_hr_payroll_user")
    l10n_in_gratuity_percentage = fields.Float(string='Gratuity Percentage', groups="hr_payroll.group_hr_payroll_user",
        compute="_compute_l10n_in_gratuity_percentage", store=True, readonly=False, digits=(16, 4),
        help='Percentage(%) to calculate gratuity amount.')
    l10n_in_gratuity = fields.Monetary(string='Gratuity', compute="_compute_l10n_in_gratuity",
        groups="hr_payroll.group_hr_payroll_user", readonly=False, store=True, tracking=True,
        help='Gratuity amount as a percentage of the basic salary.')
    l10n_in_provident_fund = fields.Boolean(related='company_id.l10n_in_provident_fund', groups="hr_payroll.group_hr_payroll_user", readonly=False)
    l10n_in_pf_employee_amount = fields.Monetary(compute="_compute_l10n_in_pf_employee_amount",
        store=True, readonly=False, tracking=True, groups="hr_payroll.group_hr_payroll_user",
        help='Employee contributes a percentage of the Basic salary + Dearness allowance.')
    l10n_in_pf_employee_percentage = fields.Float(string="Employee PF Percentage",
        compute="_compute_l10n_in_pf_employee_percentage", store=True, groups="hr_payroll.group_hr_payroll_user", readonly=False)
    l10n_in_pf_employer_amount = fields.Monetary(string="Employer", compute="_compute_l10n_in_pf_employer_amount",
        store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help='Employer contributes a percentage of the Basic salary + Dearness allowance.')
    l10n_in_pf_employer_percentage = fields.Float(string="Employer PF Percentage",
        compute="_compute_l10n_in_pf_employer_percentage", store=True, groups="hr_payroll.group_hr_payroll_user", readonly=False)
    l10n_in_pt = fields.Boolean(related='company_id.l10n_in_pt', groups="hr_payroll.group_hr_payroll_user")
    l10n_in_esic = fields.Boolean(related='company_id.l10n_in_esic', groups="hr_payroll.group_hr_payroll_user")
    l10n_in_esic_employee_amount = fields.Monetary(groups="hr_payroll.group_hr_payroll_user",
        compute="_compute_l10n_in_esic_employee_amount", store=True, readonly=False, tracking=True,
        help='Employee contributions apply when the gross wage is below ₹21,000')
    l10n_in_esic_employee_percentage = fields.Float(string='Employee ESIC Percentage',
        compute="_compute_l10n_in_esic_employee_percentage", store=True, readonly=False,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_in_esic_employer_amount = fields.Monetary(groups="hr_payroll.group_hr_payroll_user",
        compute="_compute_l10n_in_esic_employer_amount", store=True, readonly=False, tracking=True,
        help='Employer contributions apply when the gross wage is below ₹21,000')
    l10n_in_esic_employer_percentage = fields.Float(string='Employer ESIC Percentage',
        compute="_compute_l10n_in_esic_employer_percentage", store=True, readonly=False,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_in_labour_welfare = fields.Boolean(related='company_id.l10n_in_labour_welfare', groups="hr_payroll.group_hr_payroll_user")
    l10n_in_lwf_employer_contribution = fields.Monetary(groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help='LWF Employer Contribution deduction fix amount withheld from salary for the state-administered Labour\
        Welfare Fund.')
    l10n_in_lwf_employee_contribution = fields.Monetary(groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help='LWF Employee Contribution deduction fix amount withheld from salary for the state-administered Labour\
        Welfare Fund.')
# ----- end of deductions -----
    l10n_in_gross_salary = fields.Monetary(string="Gross Salary", compute="_compute_l10n_in_gross_salary", store=True,
        groups="hr_payroll.group_hr_payroll_user")
    _check_l10n_in_hra_percentage = models.Constraint(
        'CHECK(l10n_in_hra_percentage >= 0 and l10n_in_hra_percentage <= 1)',
        'House-Rent Allowance Percentage should be between 0% and 100%!'
    )
    _check_l10n_in_basic_percentage = models.Constraint(
        'CHECK(l10n_in_basic_percentage >= 0 and l10n_in_basic_percentage <= 1)',
        'Basic Salary Percentage should be between 0% and 100%!'
    )
    _check_l10n_in_standard_allowance_percentage = models.Constraint(
        'CHECK(l10n_in_standard_allowance_percentage >= 0 and l10n_in_standard_allowance_percentage <= 1)',
        'Standard Allowance Percentage should be between 0% and 100%!'
    )
    _check_l10n_in_performance_bonus_percentage = models.Constraint(
        'CHECK(l10n_in_performance_bonus_percentage >= 0 and l10n_in_performance_bonus_percentage <= 1)',
        'Performance Bonus Percentage should be between 0% and 100%!'
    )
    _check_leave_travel_percentage = models.Constraint(
        'CHECK(l10n_in_leave_travel_percentage >= 0 and l10n_in_leave_travel_percentage <= 1)',
        'Leave Travel Allowance Percentage should be between 0% and 100%!'
    )
    _check_l10n_in_gratuity_percentage = models.Constraint(
        'CHECK(l10n_in_gratuity_percentage >= 0 and l10n_in_gratuity_percentage <= 1)',
        'Gratuity Percentage should be between 0% and 100%!'
    )
    _check_l10n_in_pf_employee_percentage = models.Constraint(
        'CHECK(l10n_in_pf_employee_percentage >= 0 and l10n_in_pf_employee_percentage <= 1)',
        'Employee PF Percentage should be between 0% and 100%!'
    )
    _check_l10n_in_pf_employer_percentage = models.Constraint(
        'CHECK(l10n_in_pf_employer_percentage >= 0 and l10n_in_pf_employer_percentage <= 1)',
        'Employer PF Percentage should be between 0% and 100%!'
    )
    _check_l10n_in_esic_employee_percentage = models.Constraint(
        'CHECK(l10n_in_esic_employee_percentage >= 0 and l10n_in_esic_employee_percentage <= 1)',
        'Employee ESIC Percentage should be between 0% and 100%!'
    )
    _check_l10n_in_esic_employer_percentage = models.Constraint(
        'CHECK(l10n_in_esic_employer_percentage >= 0 and l10n_in_esic_employer_percentage <= 1)',
        'Employer ESIC Percentage should be between 0% and 100%!'
    )

    @api.constrains(
        'l10n_in_basic_salary_amount', 'l10n_in_hra', 'l10n_in_standard_allowance', 'l10n_in_performance_bonus',
        'l10n_in_leave_travel_allowance', 'wage', 'hourly_wage'
    )
    def _check_l10n_in_total_allowance_below_wage(self):
        for version in self:
            if version.company_id.country_code != 'IN':
                continue
            monthly_wage = version._l10n_in_get_montly_wage()
            total_allowance = sum([
                version.l10n_in_basic_salary_amount,
                version.l10n_in_hra,
                version.l10n_in_standard_allowance,
                version.l10n_in_performance_bonus,
                version.l10n_in_leave_travel_allowance,
            ])
            if total_allowance and total_allowance > monthly_wage:
                raise ValidationError(
                    self.env._("Sum of Basic Salary, HRA, Standard Allowance, Performance Bonus, and "
                    "Leave Travel Allowance must not exceed the monthly wage (%(monthly)s).\n Current total is %(total)s.",
                    monthly=format_amount(self.env, monthly_wage, self.env.company.currency_id),
                    total=format_amount(self.env, total_allowance, self.env.company.currency_id))
                )

    @api.depends('wage', 'hourly_wage', 'wage_type', 'resource_calendar_id.hours_per_day', 'l10n_in_basic_percentage')
    def _compute_l10n_in_basic_salary_amount(self):
        for version in self:
            monthly_wage = version._l10n_in_get_montly_wage()
            version.l10n_in_basic_salary_amount = monthly_wage * version.l10n_in_basic_percentage

    @api.depends('l10n_in_basic_salary_amount', 'wage', 'hourly_wage', 'wage_type', 'resource_calendar_id.hours_per_day')
    def _compute_l10n_in_basic_percentage(self):
        default_percentage = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_in_basic_percent', raise_if_not_found=False)
        is_hr_payroll = self.env.context.get('is_hr_payroll')
        salary_simulation = self.env.context.get('salary_simulation')
        for version in self:
            if version.company_id.country_code != 'IN':
                continue
            monthly_wage = version._l10n_in_get_montly_wage()
            if not monthly_wage:
                version.l10n_in_basic_percentage = 0.0
                continue
            if self.env.context.get('skip_percentage_calc'):
                continue
            if (not version.l10n_in_basic_salary_amount and not is_hr_payroll and salary_simulation):
                version.l10n_in_basic_percentage = default_percentage
                continue
            version.l10n_in_basic_percentage = version.l10n_in_basic_salary_amount / monthly_wage

    # ----- Allowances -----
    @api.depends('l10n_in_basic_salary_amount', 'l10n_in_hra_percentage')
    def _compute_l10n_in_hra(self):
        for version in self:
            version.l10n_in_hra = version.l10n_in_basic_salary_amount *\
                version.l10n_in_hra_percentage

    @api.depends('l10n_in_hra', 'l10n_in_basic_salary_amount')
    def _compute_l10n_in_hra_percentage(self):
        for version in self:
            if not version.l10n_in_basic_salary_amount:
                version.l10n_in_hra_percentage = 0.0
                continue
            if self.env.context.get('skip_percentage_calc'):
                continue
            version.l10n_in_hra_percentage = version.l10n_in_hra /\
                version.l10n_in_basic_salary_amount

    @api.depends('l10n_in_basic_salary_amount', 'l10n_in_standard_allowance_percentage')
    def _compute_l10n_in_standard_allowance(self):
        for version in self:
            version.l10n_in_standard_allowance = version.l10n_in_basic_salary_amount *\
                version.l10n_in_standard_allowance_percentage

    @api.depends('l10n_in_standard_allowance', 'l10n_in_basic_salary_amount')
    def _compute_l10n_in_standard_allowance_percentage(self):
        for version in self:
            if not version.l10n_in_basic_salary_amount:
                version.l10n_in_standard_allowance_percentage = 0.0
                continue
            version.l10n_in_standard_allowance_percentage = version.l10n_in_standard_allowance /\
                version.l10n_in_basic_salary_amount

    @api.depends('l10n_in_basic_salary_amount', 'l10n_in_performance_bonus_percentage')
    def _compute_l10n_in_performance_bonus(self):
        for version in self:
            version.l10n_in_performance_bonus = version.l10n_in_basic_salary_amount *\
                version.l10n_in_performance_bonus_percentage

    @api.depends('l10n_in_performance_bonus', 'l10n_in_basic_salary_amount')
    def _compute_l10n_in_performance_bonus_percentage(self):
        for version in self:
            if not version.l10n_in_basic_salary_amount:
                version.l10n_in_performance_bonus_percentage = 0.0
                continue
            if self.env.context.get('skip_percentage_calc'):
                continue
            version.l10n_in_performance_bonus_percentage = version.l10n_in_performance_bonus /\
                version.l10n_in_basic_salary_amount

    @api.depends('l10n_in_basic_salary_amount', 'l10n_in_leave_travel_percentage')
    def _compute_l10n_in_leave_travel_allowance(self):
        for version in self:
            version.l10n_in_leave_travel_allowance = version.l10n_in_basic_salary_amount *\
                version.l10n_in_leave_travel_percentage

    @api.depends('l10n_in_leave_travel_allowance', 'l10n_in_basic_salary_amount')
    def _compute_l10n_in_leave_travel_percentage(self):
        for version in self:
            if not version.l10n_in_basic_salary_amount:
                version.l10n_in_leave_travel_percentage = 0.0
                continue
            if self.env.context.get('skip_percentage_calc'):
                continue
            version.l10n_in_leave_travel_percentage = version.l10n_in_leave_travel_allowance /\
                version.l10n_in_basic_salary_amount

    @api.depends('wage', 'hourly_wage', 'resource_calendar_id.hours_per_day', 'l10n_in_basic_salary_amount',
        'l10n_in_hra', 'l10n_in_performance_bonus', 'l10n_in_leave_travel_allowance', 'l10n_in_standard_allowance')
    def _compute_l10n_in_fixed_allowance(self):
        for version in self:
            if version.l10n_in_basic_salary_amount:
                total_allowances = sum([
                    version.l10n_in_basic_salary_amount,
                    version.l10n_in_hra,
                    version.l10n_in_standard_allowance,
                    version.l10n_in_performance_bonus,
                    version.l10n_in_leave_travel_allowance,
                ])
                monthly_wage = version._l10n_in_get_montly_wage()
                version.l10n_in_fixed_allowance = monthly_wage - total_allowances

    @api.depends('l10n_in_fixed_allowance')
    def _compute_l10n_in_fixed_allowance_percentage(self):
        for version in self:
            if not version.l10n_in_basic_salary_amount:
                version.l10n_in_fixed_allowance_percentage = 0.0
                continue
            version.l10n_in_fixed_allowance_percentage = version.l10n_in_fixed_allowance /\
                version.l10n_in_basic_salary_amount

    # ----- Deductions -----
    @api.depends('l10n_in_basic_salary_amount', 'l10n_in_gratuity_percentage')
    def _compute_l10n_in_gratuity(self):
        for version in self:
            version.l10n_in_gratuity = version.l10n_in_basic_salary_amount * version.l10n_in_gratuity_percentage

    @api.depends('l10n_in_gratuity', 'l10n_in_basic_salary_amount')
    def _compute_l10n_in_gratuity_percentage(self):
        for version in self:
            if not version.l10n_in_basic_salary_amount:
                version.l10n_in_gratuity_percentage = 0.0
                continue
            if self.env.context.get('skip_percentage_calc'):
                continue
            version.l10n_in_gratuity_percentage = version.l10n_in_gratuity / version.l10n_in_basic_salary_amount

    @api.depends('l10n_in_basic_salary_amount', 'l10n_in_pf_employee_type', 'wage', 'hourly_wage')
    def _compute_l10n_in_pf_employee_amount(self):
        rule_parameter = self.env['hr.rule.parameter']
        pf_amount = rule_parameter._get_parameter_from_code('l10n_in_pf_amount', raise_if_not_found=False)
        pf_percentage = rule_parameter._get_parameter_from_code('l10n_in_pf_percent', raise_if_not_found=False)
        for version in self:
            if not (version.wage or version.hourly_wage) or\
                not (version.l10n_in_pf_employee_type in ('fixed', 'calculate') and pf_percentage):
                version.l10n_in_pf_employee_amount = 0.0
                continue
            base_amount = version.l10n_in_basic_salary_amount
            if version.l10n_in_pf_employee_type == 'fixed' and pf_amount:
                base_amount = min(base_amount, pf_amount)
            version.l10n_in_pf_employee_amount = base_amount * pf_percentage

    @api.depends('l10n_in_pf_employee_amount', 'l10n_in_basic_salary_amount')
    def _compute_l10n_in_pf_employee_percentage(self):
        for version in self:
            if version.l10n_in_basic_salary_amount:
                version.l10n_in_pf_employee_percentage = version.l10n_in_pf_employee_amount /\
                    version.l10n_in_basic_salary_amount
            else:
                version.l10n_in_pf_employee_percentage = 0.0

    @api.depends('wage', 'hourly_wage', 'l10n_in_basic_salary_amount', 'l10n_in_pf_employer_type')
    def _compute_l10n_in_pf_employer_amount(self):
        rule_parameter = self.env['hr.rule.parameter']
        pf_amount = rule_parameter._get_parameter_from_code('l10n_in_pf_amount', raise_if_not_found=False)
        pf_percentage = rule_parameter._get_parameter_from_code('l10n_in_pf_percent', raise_if_not_found=False)
        for version in self:
            if not (version.wage or version.hourly_wage) or\
            not (version.l10n_in_pf_employer_type in ('fixed', 'calculate') and pf_percentage):
                version.l10n_in_pf_employer_amount = 0.0
                continue
            base_amount = version.l10n_in_basic_salary_amount
            if version.l10n_in_pf_employer_type == 'fixed' and pf_amount:
                base_amount = min(base_amount, pf_amount)
            version.l10n_in_pf_employer_amount = base_amount * pf_percentage

    @api.depends('l10n_in_pf_employer_amount', 'l10n_in_basic_salary_amount')
    def _compute_l10n_in_pf_employer_percentage(self):
        for version in self:
            if version.l10n_in_basic_salary_amount:
                version.l10n_in_pf_employer_percentage = version.l10n_in_pf_employer_amount /\
                    version.l10n_in_basic_salary_amount
            else:
                version.l10n_in_pf_employer_percentage = 0.0

    @api.depends('l10n_in_basic_salary_amount', 'l10n_in_hra', 'l10n_in_fixed_allowance', 'l10n_in_phone_subscription',
        'l10n_in_performance_bonus', 'l10n_in_leave_travel_allowance', 'l10n_in_standard_allowance',
        'l10n_in_internet_subscription', 'l10n_in_meal_voucher_amount', 'l10n_in_company_transport')
    def _compute_l10n_in_gross_salary(self):
        for version in self:
            version.l10n_in_gross_salary = sum([version.l10n_in_basic_salary_amount, version.l10n_in_hra,
                version.l10n_in_fixed_allowance, version.l10n_in_performance_bonus, version.l10n_in_standard_allowance,
                version.l10n_in_leave_travel_allowance, version.l10n_in_phone_subscription,
                version.l10n_in_internet_subscription, version.l10n_in_meal_voucher_amount,
                version.l10n_in_company_transport])

    @api.depends('l10n_in_gross_salary', 'l10n_in_esic_employee_percentage')
    def _compute_l10n_in_esic_employee_amount(self):
        for version in self:
            if not version.l10n_in_gross_salary:
                version.l10n_in_esic_employee_amount = 0.0
                continue
            version.l10n_in_esic_employee_amount = version.l10n_in_gross_salary *\
                version.l10n_in_esic_employee_percentage

    @api.depends('l10n_in_esic_employee_amount', 'l10n_in_gross_salary')
    def _compute_l10n_in_esic_employee_percentage(self):
        for version in self:
            if not version.l10n_in_gross_salary:
                version.l10n_in_esic_employee_percentage = 0.0
                continue
            if self.env.context.get('skip_percentage_calc'):
                continue
            version.l10n_in_esic_employee_percentage = version.l10n_in_esic_employee_amount /\
                version.l10n_in_gross_salary

    @api.depends('l10n_in_gross_salary', 'l10n_in_esic_employer_percentage')
    def _compute_l10n_in_esic_employer_amount(self):
        for version in self:
            if not version.l10n_in_gross_salary:
                version.l10n_in_esic_employer_amount = 0.0
                continue
            version.l10n_in_esic_employer_amount = version.l10n_in_gross_salary *\
                version.l10n_in_esic_employer_percentage

    @api.depends('l10n_in_gross_salary', 'l10n_in_esic_employer_amount')
    def _compute_l10n_in_esic_employer_percentage(self):
        for version in self:
            if not version.l10n_in_gross_salary:
                version.l10n_in_esic_employer_percentage = 0.0
                continue
            if self.env.context.get('skip_percentage_calc'):
                continue
            version.l10n_in_esic_employer_percentage = version.l10n_in_esic_employer_amount /\
                version.l10n_in_gross_salary

    @api.depends('l10n_in_medical_insurance', 'l10n_in_insured_spouse', 'l10n_in_insured_first_children',
        'l10n_in_insured_second_children')
    def _compute_l10n_in_medical_insurance_total(self):
        for version in self:
            insured_count = 1 + sum([
                version.l10n_in_insured_spouse,
                version.l10n_in_insured_first_children,
                version.l10n_in_insured_second_children
            ])
            version.l10n_in_medical_insurance_total = version.l10n_in_medical_insurance * insured_count
# ----- end of deductions -----

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "IN":
            whitelisted_fields += [
                "l10n_in_hra_percentage", "l10n_in_hra", "l10n_in_leave_travel_percentage",
                "l10n_in_leave_travel_allowance", "l10n_in_basic_percentage", "l10n_in_basic_salary_amount",
                "l10n_in_standard_allowance", "l10n_in_standard_allowance_percentage", "l10n_in_performance_bonus",
                "l10n_in_performance_bonus_percentage", "l10n_in_fixed_allowance_percentage", "l10n_in_fixed_allowance",
                "l10n_in_phone_subscription", "l10n_in_internet_subscription", "l10n_in_meal_voucher_amount",
                "l10n_in_company_transport", "l10n_in_tds", "l10n_in_medical_insurance",
                "l10n_in_insured_spouse", "l10n_in_insured_first_children", "l10n_in_insured_second_children",
                "l10n_in_gratuity_percentage", "l10n_in_gratuity", "l10n_in_provident_fund",
                "l10n_in_pf_employee_amount", "l10n_in_pf_employee_percentage", "l10n_in_pf_employer_amount",
                "l10n_in_pf_employer_percentage", "l10n_in_pt", "l10n_in_esic", "l10n_in_esic_employee_amount",
                "l10n_in_esic_employee_percentage", "l10n_in_esic_employer_amount", "l10n_in_esic_employer_percentage",
                "l10n_in_labour_welfare", "l10n_in_lwf_employer_contribution", "l10n_in_lwf_employee_contribution",
                "pt_rule_parameter_id", "l10n_in_pf_employee_type", "l10n_in_pf_employer_type",
            ]
        return whitelisted_fields

    def _l10n_in_convert_amount(self, amount, period_from, period_to):
        PERIODS_PER_YEAR = {
            "daily": 260,
            "weekly": 52,
            "bi-weekly": 26,
            "semi-monthly": 24,
            "monthly": 12,
            "bi-monthly": 6,
            "quarterly": 4,
            "semi-annually": 2,
            "annually": 1,
        }

        NUMBER_OF_WEEKS = {
            "daily": 1 / 5,
            "weekly": 1,
            "bi-weekly": 2,
            "monthly": 13 / 3,
            "quarterly": 13,
            "annually": 13 * 4,
        }
        if period_to == "weekly":
            return amount / NUMBER_OF_WEEKS[period_from]
        coefficient = PERIODS_PER_YEAR[period_from] / PERIODS_PER_YEAR[period_to]
        return amount * round(coefficient)

    def _l10n_in_get_montly_wage(self):
        """
        Returns the monthly wage based on the wage type and resource calendar.
        """
        if self.wage_type == 'hourly':
            hours_per_day = self.resource_calendar_id.hours_per_day
            monthly_wage = self._l10n_in_convert_amount(self.hourly_wage * hours_per_day, "daily", "monthly")
        else:
            monthly_wage = self.wage
        return max(monthly_wage, 0)
