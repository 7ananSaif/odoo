# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from math import ceil

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

OVERTIME_CASUAL_LOADING_COEF = 1.25
SATURDAY_CASUAL_LOADING_COEF = 1.50
SUNDAY_CASUAL_LOADING_COEF = 1.75
PUBLIC_HOLIDAY_CASUAL_LOADING_COEF = 2.5

CESSATION_TYPE_CODE = [
    ("V", "(V) Voluntary Cessation"),
    ("I", "(I) Ill Health"),
    ("D", "(D) Deceased"),
    ("R", "(R) Redundancy"),
    ("F", "(F) Dismissal"),
    ("C", "(C) Contract Cessation"),
    ("T", "(T) Transfer"),
]
INCOME_STREAM_TYPES = [
    ("SAW", "Salary and wages"),
    ("CHP", "Closely held payees"),
    ("IAA", "Inbound assignees to Australia"),
    ("WHM", "Working holiday makers"),
    ("SWP", "Seasonal worker programme"),
    ("FEI", "Foreign employment income"),
    ("JPD", "Joint petroleum development area"),
    ("VOL", "Voluntary agreement"),
    ("LAB", "Labour hire"),
    ("OSP", "Other specified payments")]


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_au_tfn_declaration = fields.Selection(
        selection=[
            ("provided", "Declaration provided"),
            ("000000000", "Declaration not completed, employee did not provide TFN, employee promised declaration more than 28 days ago"),
            ("111111111", "Employee applied for TFN but didn't receive it yet, less than 28 days ago"),
            ("333333333", "Employee under 18 and earns less than 350$ weekly"),
            ("444444444", "Employee is recipient of social security, service pension or benefit, may be exempt from TFN")],
        string="TFN Status",
        default="000000000",
        required=True,
        groups="hr_payroll.group_hr_payroll_user",
        help="TFN Declaration status of the employee. All options except 'Declaration not completed...' will be treated as TFN provided.",
        tracking=True,
        )
    l10n_au_tfn = fields.Char(
        string="Tax File Number",
        compute="_compute_l10n_au_tfn",
        readonly=False,
        store=True,
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True,
        )
    l10n_au_nat_3093_amount = fields.Float(
        string="Annual Tax Offset",
        groups="hr_payroll.group_hr_payroll_user",
        help="Amount of tax offset the employee entered in his NAT3093 withholding declaration, 0 if the employee did not present a declaration",
        tracking=True,
        )
    l10n_au_extra_pay = fields.Boolean(
        string="Withhold for Extra Pay",
        groups="hr_payroll.group_hr_payroll_user",
        help="Whether the employee wants additional withholding in case of 53 weekly pays or 27 fortnightly pays in a year",
        tracking=True,
        )
    l10n_au_training_loan = fields.Boolean(
        string="HELP / STSL",
        groups="hr_payroll.group_hr_payroll_user",
        help="Whether the employee is a Study Training Support Loan (STSL) recipient",
        tracking=True,
        )
    l10n_au_medicare_exemption = fields.Selection(
        selection=[
            ("X", "None"),
            ("H", "Half"),
            ("F", "Full")],
        string="Medicare levy exemption",
        default="X",
        required=True,
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True,
        )
    l10n_au_medicare_surcharge = fields.Selection(
        selection=[
            ("X", "0%"),
            ("1", "1%"),
            ("2", "1.25%"),
            ("3", "1.5%")],
        string="Medicare levy surcharge",
        default="X",
        groups="hr_payroll.group_hr_payroll_user",
        required=True,
        tracking=True,
        )
    l10n_au_medicare_reduction = fields.Selection(
        selection=[
            ("X", "Not Applicable"),
            ("0", "Spouse Only"),
            ("1", "1 Child"),
            ("2", "2 Children"),
            ("3", "3 Children"),
            ("4", "4 Children"),
            ("5", "5 Children"),
            ("6", "6 Children"),
            ("7", "7 Children"),
            ("8", "8 Children"),
            ("9", "9 Children"),
            ("A", "10+ Children"),
        ],
        string="Medicare levy reduction",
        compute="_compute_l10n_au_medicare_reduction",
        store=True,
        readonly=False,
        required=True,
        default="X",
        groups="hr_payroll.group_hr_payroll_user",
        help="Medicare levy reduction, dependent on marital status and number of children",
        tracking=True,
        )
    l10n_au_tax_free_threshold = fields.Boolean(
        string="Tax-free Threshold",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True,
        )
    l10n_au_child_support_deduction = fields.Float(
        string="Child Support Deduction",
        groups="hr_payroll.group_hr_payroll_user",
        help="Amount that has to be deducted every pay period, subject to Protected Earnings Amount (PEA)",
        tracking=True,
        )
    l10n_au_child_support_garnishee_amount = fields.Float(
        string="Child Support Garnishee Amount %",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True,
        )
    l10n_au_employment_basis_code = fields.Selection(
        selection=[
            ("F", "Full time"),
            ("P", "Part time"),
            ("C", "Casual"),
            ("L", "Labour hire"),
            ("V", "Voluntary agreement"),
            ("D", "Death beneficiary"),
            ("N", "Non-employee")],
        string="Employment Type",
        default="F",
        required=True,
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True
    )
    l10n_au_tax_treatment_category = fields.Selection(
        selection=[
            ("R", "Regular"),
            ("A", "Actor"),
            ("C", "Horticulture & Shearing"),
            ("S", "Seniors & Pensioners"),
            ("H", "Working Holiday Makers"),
            ("W", "Seasonal Worker Program"),
            ("F", "Foreign Resident"),
            ("N", "No TFN"),
            ("D", "ATO-defined"),
            ("V", "Voluntary Agreement")],
        default="R",
        required=True,
        string="Tax Treatment Category",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True,
        )
    l10n_au_income_stream_type = fields.Selection(
        selection=INCOME_STREAM_TYPES,
        string="Income Stream Type", default="SAW",
        compute="_compute_l10n_au_income_stream_type",
        precompute=True,
        store=True, readonly=False, required=True,
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True,
        )
    l10n_au_tax_treatment_option_actor = fields.Selection(
        selection=[
            ("D", "Daily Performer"),
            ("P", "Promotional Activity")
        ], string="Actor Option", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_less_than_3_performance = fields.Boolean(string="Less than 3 Performances", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_tax_treatment_option_voluntary = fields.Selection(
        selection=[
            ("C", "Commissioner's Instalment Rate"),
            ("O", "Other Rate"),
        ], string="Voluntary Agreement Option", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_tax_treatment_option_seniors = fields.Selection(
        selection=[
            ("S", "Single"),
            ("M", "Married"),
            ("I", "Illness-separated"),
        ], string="Seniors Option", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_comissioners_installment_rate = fields.Float(
        string="Commissioner's Instalment Rate", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_tax_treatment_code = fields.Char(
        string="Tax Code", store=True,
        compute="_compute_l10n_au_tax_treatment_code",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True,
    )
    l10n_au_work_country_id = fields.Many2one(
        "res.country", string="Country", help="Country where the work is performed", groups="hr_payroll.group_hr_payroll_user", tracking=True
    )
    l10n_au_withholding_variation = fields.Selection(
        selection=[
            ("none", "None"),
            ("salaries", "Salaries"),
            ("leaves", "Salaries and Unused Leaves"),
        ],
        string="Withholding Variation",
        default="none",
        groups="hr_payroll.group_hr_payroll_user",
        required=True,
        help="Employee has a custom withholding rate.",
        tracking=True,
    )
    l10n_au_withholding_variation_amount = fields.Float(string="Withholding Variation Rate", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_additional_withholding_amount = fields.Monetary(
        string="Additional Withholding Amount",
        groups="hr_payroll.group_hr_payroll_user",
        help="Additional amount will be withheld from the employee's salary after PAYG withholding. (Schedule 14)",
        tracking=True,
        )
    l10n_au_casual_loading = fields.Float(string="Casual Loading", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_pay_day = fields.Selection(
        selection=[
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday")],
        string="Regular Pay Day", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_eligible_for_leave_loading = fields.Boolean(string="Eligible for Leave Loading", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_leave_loading = fields.Selection(
        selection=[
            ("regular", "Regular"),
            ("once", "Lump Sum")],
        string="Leave Loading", groups="hr_payroll.group_hr_payroll_user",
        help="How leave loading, if any, is to be paid. If Lump Sum is selected, leave loading will not be added to regular payslips automatically",
        tracking=True,
        )
    l10n_au_leave_loading_leave_types = fields.Many2many(
        "hr.leave.type",
        string="Leave Types for Leave Loading", groups="hr_payroll.group_hr_payroll_user",
        help="Leave Types that should be taken into account for leave loading, both regular and lump sum.",
        tracking=True,
        )
    l10n_au_leave_loading_rate = fields.Float(string="Leave Loading Rate (%)", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_cessation_type_code = fields.Selection(
        CESSATION_TYPE_CODE,
        string="Cessation Type", groups="hr_payroll.group_hr_payroll_user",
        help="""
            "V": an employee resignation, retirement, domestic or pressing necessity or abandonment of employment.
            "I": an employee resignation due to medical condition that prevents the continuation of employment, such as for illness, ill-health, medical unfitness or total permanent disability.
            "D": the death of an employee.
            "R": an employer-initiated termination of employment due to a genuine bona-fide redundancy or approved early retirement scheme.
            "F": an employer-initiated termination of employment due to dismissal, inability to perform the required work, misconduct or inefficiency.
            "C": the natural conclusion of a limited employment relationship due to contract/engagement duration or task completion, seasonal work completion, or to cease casuals that are no longer required.
            "T": the administrative arrangements performed to transfer employees across payroll systems, move them temporarily to another employer (machinery of government for public servants), transfer of business, move them to outsourcing arrangements or other such technical activities.
        """,
        tracking=True,
        )
    l10n_au_performances_per_week = fields.Integer(string="Performances per week", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_workplace_giving = fields.Float(string="Workplace Giving Employee", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_workplace_giving_employer = fields.Float(string="Salary Sacrificed Workplace Giving", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_salary_sacrifice_superannuation = fields.Float(string="Salary Sacrifice Superannuation", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_salary_sacrifice_other = fields.Float(string="Salary Sacrifice Other Benefits", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_au_extra_negotiated_super = fields.Float(string="Extra Negotiated Super %", groups="hr_payroll.group_hr_payroll_user",
        help="This is an additional Super Contribution negotiated by the employee. Paid by employer. (RESC)", tracking=True)
    l10n_au_extra_compulsory_super = fields.Float(string="Extra Compulsory Super %", groups="hr_payroll.group_hr_payroll_user",
        help="This is an additional Compulsory Super Contribution required by the fund or territory law. (Not RESC)", tracking=True)
    l10n_au_yearly_wage = fields.Monetary(string="Yearly Wage", compute="_compute_yearly_wage", inverse="_inverse_yearly_wages", readonly=False, store=True, groups="hr_payroll.group_hr_payroll_user", tracking=True)
    wage = fields.Monetary(compute="_compute_wage", readonly=False, store=True, tracking=True)
    hourly_wage = fields.Monetary(compute="_compute_hourly_wage", readonly=False, store=True, tracking=True)

    _l10n_au_casual_loading_span = models.Constraint(
        'CHECK(l10n_au_casual_loading >= 0 AND l10n_au_casual_loading <= 1)',
        "The casual loading is a percentage and should have a value between 0 and 100.",
    )
    _l10n_au_extra_negotiated_super_span = models.Constraint(
        'CHECK(l10n_au_extra_negotiated_super >= 0 AND l10n_au_extra_negotiated_super <= 1)',
        "The Extra Negotiated super is a percentage and should have a value between 0 and 100.",
    )
    _l10n_au_extra_compulsory_super_span = models.Constraint(
        'CHECK(l10n_au_extra_compulsory_super >= 0 AND l10n_au_extra_compulsory_super <= 1)',
        "The Extra Compulsory super is a percentage and should have a value between 0 and 100.",
    )
    _l10n_au_child_support_garnishee_amount_span = models.Constraint(
        'CHECK(l10n_au_child_support_garnishee_amount >= 0 AND l10n_au_child_support_garnishee_amount <= 1)',
        "Child Support Garnishee is a percentage and should have a value between 0 and 100.",
    )

    @api.constrains('employee_id', 'schedule_pay')
    def _check_l10n_au_schedule_pay(self):
        allowed_schedule_pay = ('daily', 'weekly', 'bi-weekly', 'monthly', 'quarterly')
        for version in self:
            if version.country_code == 'AU' and version.schedule_pay not in allowed_schedule_pay:
                raise UserError(_('Australian contracts are only supported for daily, weekly, fortnightly, monthly and quarterly pay schedules.'))

    @api.constrains("private_country_id", "l10n_au_income_stream_type")
    def _check_l10n_au_work_country(self):
        for rec in self:
            if rec.country_id.code in ["AU", False] and rec.l10n_au_income_stream_type in ["IAA", "WHM"]:
                raise ValidationError(_(
                    "Inbound assignees to Australia and Working Holiday Makers must have a Nationality set other than Australia."
                ))

    @api.constrains(
        "l10n_au_tax_treatment_category",
        "l10n_au_income_stream_type",
        "l10n_au_tfn_declaration",
        "l10n_au_tax_free_threshold",
        "is_non_resident",
    )
    def _check_l10n_au_tax_treatment(self):
        for rec in self:
            if rec.country_code != "AU":
                continue
            # TFN Declaration Constraints
            elif rec.l10n_au_tfn_declaration != "000000000" and rec.l10n_au_tax_treatment_category == "N":
                raise ValidationError(_("The Employee has a TFN provided so the No TFN tax treatment category cannot be used."))
            # Tax-Free Threshold Constraints
            if rec.is_non_resident and rec.l10n_au_tax_free_threshold:
                raise ValidationError(_("A foreign resident cannot claim the tax-free threshold"))
            # Tax treatment category constraints
            if rec.l10n_au_tax_treatment_category == "V" and rec.l10n_au_income_stream_type != "VOL":
                raise ValidationError(_("Income Stream Type should be VOL for Tax Treatment Category V."))
            elif rec.l10n_au_tax_treatment_category == "H" and rec.l10n_au_income_stream_type != "WHM":
                raise ValidationError(_("Income Stream Type should be WHM for Tax Treatment Category H."))
            elif rec.l10n_au_tax_treatment_category == "C":
                if not (rec.l10n_au_tax_free_threshold or rec.is_non_resident):
                    raise ValidationError(_("Horticulturist must claim the Tax-free Threshold or be a Foreign Resident."))
            elif rec.l10n_au_tax_treatment_category == "W" and rec.l10n_au_income_stream_type != "SWP":
                raise ValidationError(_("Income Stream Type should be SWP for Tax Treatment Category W."))
            elif rec.l10n_au_tax_treatment_category == "S" and rec.is_non_resident:
                raise ValidationError(_("Seniors cannot be a foreign resident for tax purposes"))
            elif rec.l10n_au_tax_treatment_category == "F" and not rec.is_non_resident:
                raise ValidationError(_("Employees with Foreign Resident tax category must be a foreign resident for tax purposes."))

    @api.constrains(
        'l10n_au_tax_treatment_category',
        'l10n_au_tax_treatment_option_actor',
        'l10n_au_tax_treatment_option_voluntary',
        'l10n_au_tax_treatment_option_seniors',
        'l10n_au_employment_basis_code',
    )
    def _check_l10n_au_tax_treatment_option(self):
        for rec in self:
            if rec.l10n_au_tax_treatment_category == "V" and not rec.l10n_au_tax_treatment_option_voluntary:
                raise ValidationError(_("Voluntary Agreement Option is required for Tax Treatment Category Voluntary Agreement"))
            elif rec.l10n_au_tax_treatment_category == "S" and not rec.l10n_au_tax_treatment_option_seniors:
                raise ValidationError(_("Seniors Option is required for Tax Treatment Category Seniors & Pensioners"))
            if rec.l10n_au_employment_basis_code == "V" and rec.l10n_au_tax_treatment_category != "V":
                raise ValidationError(_("To use the Voluntary Employment Type you must be using the Voluntary Tax Treatment Category."))

    @api.constrains(
        "l10n_au_training_loan",
        "l10n_au_tax_treatment_category",
        "l10n_au_medicare_surcharge",
        "l10n_au_medicare_exemption",
        "l10n_au_medicare_reduction",
        "l10n_au_tfn_declaration",
        "l10n_au_tax_free_threshold")
    def _check_l10n_au_loan_and_medicare(self):
        for rec in self:
            if rec.l10n_au_medicare_surcharge != "X" and (rec.l10n_au_medicare_reduction != 'X' or rec.l10n_au_medicare_exemption != 'X'):
                raise ValidationError(_("Employees cannot claim both a surcharge and exemption/reduction for Medicare levy"))
            if rec.l10n_au_medicare_exemption == 'F' and rec.l10n_au_medicare_reduction != 'X':
                raise ValidationError(_("Medicare levy reduction is not possible if full exemption is claimed!"))
            if rec.l10n_au_medicare_reduction != 'X' and not rec.l10n_au_tax_free_threshold and rec.l10n_au_tfn_declaration != "000000000":
                raise ValidationError(_("Medicare levy reduction is only allowed for employees who have claimed tax-free threshold "
                    "and have not provided a TFN."))
            if rec.l10n_au_tax_treatment_category not in ["R", "S"]:
                if rec.l10n_au_tax_treatment_category != "F" and rec.l10n_au_training_loan:
                    raise ValidationError(_("Training loan is only available for Regular and Seniors & Pensioners and Foreign Residents"))
                if rec.l10n_au_medicare_surcharge != 'X' or rec.l10n_au_medicare_exemption != 'X' or rec.l10n_au_medicare_reduction != 'X':
                    raise ValidationError(_("Medicare surcharge, exemption and reduction are only available for Regular and Seniors & Pensioners"))

    @api.constrains('l10n_au_tfn')
    def _check_l10n_au_tfn(self):
        def validate_tfn(tfn):
            # Source: https://clearwater.com.au/code/tfn
            # Checksum
            weights = [1, 4, 3, 7, 5, 8, 6, 9, 10]
            tfn = re.sub(r'/[^\d]/', '', tfn)
            if len(tfn) == 9:
                sum = 0
                for i, t in enumerate(tfn):
                    sum += int(t) * weights[i]
                return sum % 11 == 0
            return False

        for version in self:
            if version.l10n_au_tfn_declaration != "provided":
                continue
            if version.l10n_au_tfn and (len(version.l10n_au_tfn) < 8 or not version.l10n_au_tfn.isdigit()):
                raise ValidationError(_("The TFN must be at least 8 characters long and contain only numbers."))
            if version.l10n_au_tfn and not validate_tfn(version.l10n_au_tfn):
                raise ValidationError(_("The TFN %s is not valid. Please provide a valid TFN.", version.l10n_au_tfn))

    def write(self, vals):
        if 'l10n_au_tax_treatment_category' in vals and vals.get('l10n_au_tax_treatment_category') != 'H':
            vals['l10n_au_nat_3093_amount'] = 0
        return super().write(vals)

    @api.depends('l10n_au_tax_treatment_category')
    def _compute_l10n_au_income_stream_type(self):
        for rec in self:
            # rec.l10n_au_income_stream_type = "SAW"
            if rec.l10n_au_tax_treatment_category == "V":
                rec.l10n_au_income_stream_type = "VOL"
            elif rec.l10n_au_tax_treatment_category == "H":
                rec.l10n_au_income_stream_type = "WHM"
            elif rec.l10n_au_tax_treatment_category == "W":
                rec.l10n_au_income_stream_type = "SWP"
            else:
                rec.l10n_au_income_stream_type = rec.l10n_au_income_stream_type

    @api.depends(
        "l10n_au_tax_treatment_category",
        "l10n_au_employment_basis_code",
        "l10n_au_medicare_surcharge",
        "l10n_au_medicare_exemption",
        "l10n_au_medicare_reduction",
        "l10n_au_tax_free_threshold",
        "l10n_au_training_loan",
        "l10n_au_tfn_declaration",
        "is_non_resident",
        "l10n_au_tax_treatment_option_actor",
        "l10n_au_less_than_3_performance",
        "l10n_au_tax_treatment_option_voluntary",
        "l10n_au_tax_treatment_option_seniors",
        "company_id.l10n_au_registered_for_whm")
    def _compute_l10n_au_tax_treatment_code(self):
        for rec in self:
            code = rec.l10n_au_tax_treatment_category  # First character
            code += rec._get_second_code()  # Second Character
            # Third Character
            if rec.l10n_au_tax_treatment_category in ["R", "S", "F"] and rec.l10n_au_employment_basis_code != "D" and rec.l10n_au_training_loan:
                code += "S"
            else:
                code += "X"
            if rec.l10n_au_tax_treatment_category in ["R", "S"]:
                code += rec.l10n_au_medicare_surcharge  # Fourth Character
                code += rec.l10n_au_medicare_exemption  # Fifth Character
                code += rec.l10n_au_medicare_reduction  # Sixth Character
            else:
                code += 'XXX'
            rec.l10n_au_tax_treatment_code = code

    def _get_second_code(self) -> str:
        self.ensure_one()
        match self.l10n_au_tax_treatment_category:
            case "R":
                if self.l10n_au_employment_basis_code == "C":
                    code = "D"
                elif self.l10n_au_tax_free_threshold:
                    code = "T"
                else:
                    code = "N"
            case "A":
                if self.l10n_au_tax_treatment_option_actor == "P":
                    code = "P"
                # If actor option is Daily Performer
                elif not self.l10n_au_tax_free_threshold:
                    code = "N"
                else:
                    code = "D" if self.l10n_au_less_than_3_performance else "T"
            case "C":
                if self.is_non_resident:
                    code = "F"
                else:
                    code = "T"
            case "S":
                code = self.l10n_au_tax_treatment_option_seniors
                if self.l10n_au_tfn_declaration == "000000000":
                    code = "F"
            case "H":
                if self.l10n_au_tfn_declaration == "000000000":
                    code = "F"
                elif self.company_id.l10n_au_registered_for_whm:
                    code = "R"
                else:
                    code = "U"
            case "W":
                code = "P"
            case "F":
                code = "F"
            case "N":
                code = "F" if self.is_non_resident else "A"
            case "D":
                if self.l10n_au_employment_basis_code == "N":
                    code = "C"
                elif self.l10n_au_employment_basis_code == "D":
                    code = "B"
                else:
                    code = "V"
            case "V":
                code = self.l10n_au_tax_treatment_option_voluntary

        return str(code)

    @api.depends("l10n_au_tfn_declaration")
    def _compute_l10n_au_tfn(self):
        for version in self:
            if version.l10n_au_tfn_declaration != "provided":
                version.l10n_au_tfn = version.l10n_au_tfn_declaration
            else:
                version.l10n_au_tfn = ""

    @api.depends("marital", "children", "l10n_au_tax_free_threshold")
    def _compute_l10n_au_medicare_reduction(self):
        for version in self:
            version.l10n_au_medicare_reduction = "X"
            if version.marital in ["married", "cohabitant"] and version.l10n_au_tax_free_threshold:
                if not version.children:
                    version.l10n_au_medicare_reduction = "0"
                elif version.children < 10:
                    version.l10n_au_medicare_reduction = str(version.children)
                else:
                    version.l10n_au_medicare_reduction = "A"

    @api.depends("wage_type", "hourly_wage", "schedule_pay")
    def _compute_wage(self):
        Payslip = self.env['hr.payslip']
        for version in self:
            if version.country_code != "AU" or version.wage_type != "hourly":
                continue
            daily_wage = version.hourly_wage * version.resource_calendar_id.hours_per_day
            version.wage = Payslip._l10n_au_convert_amount(daily_wage, "daily", version.schedule_pay)

    @api.depends("wage_type", "wage")
    def _compute_hourly_wage(self):
        Payslip = self.env['hr.payslip']
        for version in self:
            if version.country_code != "AU" or version.wage_type == "hourly":
                continue
            hours_per_day = version.resource_calendar_id.hours_per_day
            daily_wage = Payslip._l10n_au_convert_amount(version.wage, version.schedule_pay, "daily")
            version.hourly_wage = daily_wage / hours_per_day

    @api.depends("wage_type", "wage", "hourly_wage", "schedule_pay")
    def _compute_yearly_wage(self):
        Payslip = self.env['hr.payslip']
        for version in self:
            if version.country_code != "AU":
                continue
            hours_per_day = version.resource_calendar_id.hours_per_day
            if version.wage_type == "hourly":
                version.l10n_au_yearly_wage = Payslip._l10n_au_convert_amount(version.hourly_wage * hours_per_day, "daily", "annually")
            else:
                version.l10n_au_yearly_wage = Payslip._l10n_au_convert_amount(version.wage, version.schedule_pay, "annually")

    def _inverse_yearly_wages(self):
        if self.country_code != "AU":
            return
        hours_per_day = self.resource_calendar_id.hours_per_day
        self.wage = self.env['hr.payslip']._l10n_au_convert_amount(self.l10n_au_yearly_wage, "annually", self.schedule_pay)
        self.hourly_wage = self.env['hr.payslip']._l10n_au_convert_amount(self.l10n_au_yearly_wage, "annually", "daily") / hours_per_day

    def get_hourly_wages(self):
        self.ensure_one()
        return {
            "overtime": self.hourly_wage * (OVERTIME_CASUAL_LOADING_COEF + self.l10n_au_casual_loading),
            "saturday": self.hourly_wage * (SATURDAY_CASUAL_LOADING_COEF + self.l10n_au_casual_loading),
            "sunday": self.hourly_wage * (SUNDAY_CASUAL_LOADING_COEF + self.l10n_au_casual_loading),
            "public_holiday": self.hourly_wage * (PUBLIC_HOLIDAY_CASUAL_LOADING_COEF + self.l10n_au_casual_loading),
        }

    @api.model
    def _l10n_au_get_financial_year_start(self, date):
        if date.month < 7:
            return date + relativedelta(years=-1, month=7, day=1)
        return date + relativedelta(month=7, day=1)

    @api.model
    def _l10n_au_get_financial_year_end(self, date):
        if date.month < 7:
            return date + relativedelta(month=6, day=30)
        return date + relativedelta(years=1, month=6, day=30)

    @api.model
    def _l10n_au_get_weeks_amount(self, date=False):
        """ Returns the amount of pay weeks in the current financial year.
        In leap years, there will be an additional week/fortnight.
        """
        target_day = date or fields.Date.context_today(self)
        start_day = self._l10n_au_get_financial_year_start(target_day)
        end_day = self._l10n_au_get_financial_year_end(target_day) + relativedelta(day=30)
        return ceil((end_day - start_day).days / 7)

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template()
        if self.env.company.country_id.code == 'AU':
            whitelisted_fields += [
                "l10n_au_casual_loading",
                "l10n_au_cessation_type_code",
                "l10n_au_eligible_for_leave_loading",
                "l10n_au_extra_compulsory_super",
                "l10n_au_extra_negotiated_super",
                "l10n_au_leave_loading",
                "l10n_au_leave_loading_leave_types",
                "l10n_au_leave_loading_rate",
                "l10n_au_pay_day",
                "l10n_au_performances_per_week",
                "l10n_au_salary_sacrifice_other",
                "l10n_au_salary_sacrifice_superannuation",
                "l10n_au_workplace_giving",
                "l10n_au_workplace_giving_employer",
                "l10n_au_yearly_wage",
            ]
        return whitelisted_fields
