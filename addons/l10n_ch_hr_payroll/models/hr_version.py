from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
import re

CANTONS_WITH_EX = [
    ('EX', 'EX - Foreign'),
    ('AG', 'Argovie'),
    ('AI', 'Appenzell Rhodes-Intérieures'),
    ('AR', 'Appenzell Rhodes-Extérieures'),
    ('BE', 'Berne'),
    ('BL', 'Bâle-Campagne'),
    ('BS', 'Bâle-Ville'),
    ('FR', 'Fribourg'),
    ('GE', 'Genève'),
    ('GL', 'Glaris'),
    ('GR', 'Grisons'),
    ('JU', 'Jura'),
    ('LU', 'Lucerne'),
    ('NE', 'Neuchâtel'),
    ('NW', 'Nidwald'),
    ('OW', 'Obwald'),
    ('SG', 'Saint-Gall'),
    ('SH', 'Schaffhouse'),
    ('SO', 'Soleure'),
    ('SZ', 'Schwytz'),
    ('TG', 'Thurgovie'),
    ('TI', 'Tessin'),
    ('UR', 'Uri'),
    ('VD', 'Vaud'),
    ('VS', 'Valais'),
    ('ZG', 'Zoug'),
    ('ZH', 'Zurich'),
]

CANTONS = [
    ('AG', 'Argovie'),
    ('AI', 'Appenzell Rhodes-Intérieures'),
    ('AR', 'Appenzell Rhodes-Extérieures'),
    ('BE', 'Berne'),
    ('BL', 'Bâle-Campagne'),
    ('BS', 'Bâle-Ville'),
    ('FR', 'Fribourg'),
    ('GE', 'Genève'),
    ('GL', 'Glaris'),
    ('GR', 'Grisons'),
    ('JU', 'Jura'),
    ('LU', 'Lucerne'),
    ('NE', 'Neuchâtel'),
    ('NW', 'Nidwald'),
    ('OW', 'Obwald'),
    ('SG', 'Saint-Gall'),
    ('SH', 'Schaffhouse'),
    ('SO', 'Soleure'),
    ('SZ', 'Schwytz'),
    ('TG', 'Thurgovie'),
    ('TI', 'Tessin'),
    ('UR', 'Uri'),
    ('VD', 'Vaud'),
    ('VS', 'Valais'),
    ('ZG', 'Zoug'),
    ('ZH', 'Zurich'),
]


tax_id_pattern = r"[A-Z]{6}[0-9]{2}(A|B|C|D|E|H|L|M|P|R|S|T)[0-9]{2}[A-Z]{1}[0-9]{3}[A-Z]{1}"


class HrVersion(models.Model):
    _inherit = 'hr.version'

    def _get_contract_type_domain(self):
        if self.env.company.country_id.code == "CH":
            return [('id', 'in', self._get_allowed_contract_type_ids())]
        return []

    l10n_ch_country_id_code = fields.Char(string="Nationality Country Code", related='country_id.code', groups="hr.group_hr_user")
    l10n_ch_po_box = fields.Char(string="PO. Box", groups="hr.group_hr_user", tracking=True)
    l10n_ch_no_nationality = fields.Selection(selection=[("11", "11 - Unknown"),
                                                         ("22", "22 - Stateless")], string="Special Nationality Status", groups="hr.group_hr_user", tracking=True)
    l10n_ch_tax_scale_type = fields.Selection(string="Tax Scale Type", selection=[('TaxAtSourceCode', 'Tariff Code'),
                                                                                  ('CategoryPredefined', "Predefined Category"),
                                                                                  ('CategoryOpen', "Open")], default="TaxAtSourceCode", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_pre_defined_tax_scale = fields.Selection(string="Predefined Tax Scale",
                                                     selection=[('NON', "NON - Not Subject to Source Tax, without Church Tax"),
                                                                ('NOY', "NOY - Not Subject to Source Tax, with Church Tax"),
                                                                ('HEN', "HEN - Honorary Board of Directors residing abroad, without Church tax"),
                                                                ('HEY', "HEY - Honorary Board of Directors residing abroad, with Church tax"),
                                                                ('MEN', "MEN - Monetary Value Services residing abroad, without Church tax"),
                                                                ('MEY', "MEY - Monetary Value Services residing abroad, with Church tax"),
                                                                ('SFN', "SFN - Special Agreement with France Tariff")
                                                                ], groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_open_tax_scale = fields.Char(string="Open Tax Scale", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_tax_specially_approved = fields.Boolean(string="Specially Approved by the ACI", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_tax_code = fields.Char(string="Source Tax Code", compute="_compute_l10n_ch_tax_code", groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_source_tax_canton = fields.Char(string="Source Tax Canton", compute="_compute_l10n_ch_source_tax_canton", groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_source_tax_municipality = fields.Char(string="Source Tax Municipality", compute="_compute_l10n_ch_source_tax_municipality", groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_concubinage = fields.Selection(string="Concubinage", selection=[("NoConcubinage", "No"),
                                                                            ("SoleCustody", "Yes with the sole custody"),
                                                                            ("ShareCustodyAndHigherIncome", "Yes with a shared custody and higher income"),
                                                                            ("AdultChildAndHigherIncome", "Yes, with an Adult Child and higher income")], default="NoConcubinage", groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_first_name = fields.Char(string="Spouse First Name", groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_last_name = fields.Char(string="Spouse Last Name", groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_birthday = fields.Date(string="Spouse Birthday", groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_street = fields.Char(groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_zip = fields.Char(groups="hr.group_hr_user", tracking=True, string="Spouse Residence ZIP-Code")
    l10n_ch_spouse_city = fields.Char(string="Spouse Residence City", groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_country_id = fields.Many2one('res.country', groups="hr.group_hr_user", tracking=True, string="Spouse Residence Country")
    l10n_ch_spouse_revenues = fields.Boolean(string="Spouse Has Income", groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_work_end_date = fields.Date(groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_residence_canton = fields.Selection(string="Spouse Residence Canton", selection=CANTONS_WITH_EX, groups="hr.group_hr_user", tracking=True)
    l10n_ch_cross_border_commuter = fields.Boolean(string="Cross Border Commuter", groups="hr.group_hr_user", tracking=True)
    l10n_ch_foreign_tax_id = fields.Char(string="Foreign Tax-ID", groups="hr.group_hr_user", tracking=True)
    l10n_ch_cross_border_start = fields.Date(string="Cross Border Commuter Start Date", groups="hr.group_hr_user", tracking=True)
    l10n_ch_agricole_company = fields.Boolean(related="company_id.l10n_ch_agricole_company", tracking=True, groups="hr.group_hr_user")
    l10n_ch_relationship_ceo = fields.Selection(string="Degree of Relationship with the owner",
                                                selection=[("unknown", "Unknown"),
                                                           ("unrelated", "Unrelated to the owner"),
                                                           ("OwnerWife", "Wife of the owner"),
                                                           ("OwnerHusband", "Husband of the owner"),
                                                           ("OwnerBloodRelation", "Blood relative with the owner"),
                                                           ("OwnerSiblings", "Siblings with the owner"),
                                                           ("OwnerFosterChild", "Foster Child of the owner")], tracking=True, default="unknown", groups="hr.group_hr_user")
    l10n_ch_other_employment = fields.Boolean(string="Other Employment", tracking=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_total_activity_type = fields.Selection(string="Other Employment Details", selection=[("unknown", "Unknown"),
                                                                                                 ("percentage", "Total Percentage"),
                                                                                                 ("gross", "Total Gross Monthly Income")], default="unknown", tracking=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_other_activity_percentage = fields.Float(string="Total Percentage", tracking=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_other_activity_gross = fields.Float(string="Total Income", tracking=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_working_days_in_ch = fields.Float(string="Working Days in Switzerland", default=20, tracking=True, groups="hr.group_hr_user")
    l10n_ch_residence_type = fields.Selection(string="Kind of residence", selection=[("Daily", "Daily"),
                                                                                     ("Weekly", "Weekly")],
                                              default="Daily", groups="hr.group_hr_user",
                                              help="""
    Daily:
    For PIS (Persons subject to Source tax) who do not have a residence or a place of stay in Switzerland,
    the registered office or permanent establishment of the company is decisive.
    This also applies notably to predefined categories (e.g., board member fees, exported employee participations, and special agreements with France).

    Weekly:
    For PIS who do not have a residence but have a weekly place of stay in Switzerland,
    the canton and municipality of the weekly stay (based on the address of the weekly stay) are decisive.
    """, tracking=True)
    l10n_ch_weekly_residence_canton = fields.Selection(string="Weekly Residence Canton", selection=CANTONS, compute="_compute_weekly_residence_autocomplete", store=True, readonly=False, tracking=True, groups="hr.group_hr_user")
    l10n_ch_weekly_residence_municipality = fields.Char(string="Weekly Residence Municipality", compute="_compute_weekly_residence_autocomplete", store=True, readonly=False, tracking=True, groups="hr.group_hr_user")

    l10n_ch_weekly_residence_address_street = fields.Char(string="Weekly Residence Street", tracking=True, groups="hr.group_hr_user")
    l10n_ch_weekly_residence_address_city = fields.Char(string="Weekly Residence City", compute="_compute_weekly_residence_autocomplete", store=True, readonly=False, tracking=True, groups="hr.group_hr_user")
    l10n_ch_weekly_residence_address_zip = fields.Char(string="Weekly Residence ZIP-Code", tracking=True, groups="hr.group_hr_user")

    l10n_ch_flex_profiling = fields.Char("Flex Profiling", help="""
    This variable can only be provided if a prior agreement has been established between the OFS and the company as part of the Profiling process.
    It involves additional information required to account for the specific characteristics of certain companies (e.g., to define the staff included).
    """, tracking=True, groups="hr.group_hr_user")

    l10n_ch_canton = fields.Selection(selection=CANTONS_WITH_EX, string="Canton", groups="hr.group_hr_user", compute="_compute_autocomplete_private_address", store=True, readonly=False, tracking=True)
    l10n_ch_tax_scale = fields.Selection([
        ('A', 'A - Scale for single people'),
        ('B', 'B - Scale for married couples living in a common household with only one spouse is gainfully employed'),
        ('C', 'C - Scale for married couples with two incomes'),
        ('D', 'D - Scale for people whose AVS contributions are reimbursed'),
        ('E', 'E - Scale for income taxed under the procedure of simplified count'),
        ('F', 'F - Scale for Italian cross-border commuters whose spouse is working lucrative outside Switzerland'),
        ('G', 'G - Scale for income acquired as compensation which is paid to persons subject to withholding tax by a person other than that the employer'),
        ('H', 'H - Scale for single people living together with children or needy persons whom they take on maintenance essentials'),
        ('L', 'L - Scale for German cross-border commuters who fulfill the conditions of the scale A'),
        ('M', 'M - Scale for German cross-border commuters who fulfill the conditions of the scale B'),
        ('N', 'N - Scale for German cross-border commuters who fulfill the conditions of the scale C'),
        ('P', 'P - Scale for German cross-border commuters who fulfill the conditions of the scale H'),
        ('Q', 'Q - Scale for German cross-border commuters who fulfill the conditions of the scale G'),
        ('R', 'R - Scale for Italian cross-border commuters who fulfill the conditions of the scale A'),
        ('S', 'S - Scale for Italian cross-border commuters who fulfill the conditions of the scale B'),
        ('T', 'T - Scale for Italian cross-border commuters who fulfill the conditions of the scale C'),
        ('U', 'U - Scale for Italian cross-border commuters who fulfill the conditions of the scale H'),
    ], string="Swiss Tax Scale", groups="hr_payroll.group_hr_payroll_user", tracking=True, default='A')
    l10n_ch_municipality = fields.Char(string="Municipality ID", compute="_compute_autocomplete_private_address", store=True, readonly=False, groups="hr.group_hr_user", tracking=True)
    private_city = fields.Char(compute="_compute_autocomplete_private_address", store=True, readonly=False)

    l10n_ch_religious_denomination = fields.Selection([
        ('romanCatholic', 'Roman Catholic'),
        ('christianCatholic', 'Christian Catholic'),
        ('reformedEvangelical', 'Reformed Evangelical'),
        ('jewishCommunity', 'Jewish Community'),
        ('otherOrNone', 'Other or None'),
    ], default='otherOrNone', string="Religious Denomination", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_church_tax = fields.Boolean(string="Swiss Church Tax", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    marital = fields.Selection(selection='_get_marital_status_selection')
    l10n_ch_marital_from = fields.Date(string="Marital Status Start Date", groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_sv_as_number = fields.Char(string="Spouse SV-AS-Number", groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_work_canton = fields.Selection(string="Spouse Work Canton", selection=CANTONS_WITH_EX, groups="hr.group_hr_user", tracking=True)
    l10n_ch_spouse_work_start_date = fields.Date(string="Spouse Work Start Date", groups="hr.group_hr_user", tracking=True)
    l10n_ch_has_withholding_tax = fields.Boolean(
        string="Pay Withholding Taxes", groups="hr.group_hr_user", tracking=True)

    l10n_ch_residence_category = fields.Selection([
        ('shortTerm-L', 'Short Term (Cat. L)'),
        ('annual-B', 'Annual (Cat. B)'),
        ('settled-C', 'Settled (Cat. C)'),
        ('crossBorder-G', 'Cross Border (Cat. G)'),
        ('asylumSeeker-N', 'Asylum Seeker (Cat. N)'),
        ('needForProtection-S', 'Need For Protection (Cat. S)'),
        ('NotificationProcedureForShorttermWork90Days', 'Notification Procedure for Short Term Work (90 days)'),
        ('NotificationProcedureForShorttermWork120Days', 'Notification Procedure for Short Term Work (120 days)'),
        ('ProvisionallyAdmittedForeigners-F', 'Provisionally Admitted Foreigners (Cat. F)'),
        ('ResidentForeignNationalWithGainfulEmployment-Ci', 'Residence Permit with Gainful Employment (Ci)'),
        ('othersNotSwiss', 'Other (Without Swiss)'),
    ], string="Residence Category", groups="hr.group_hr_user", tracking=True)

    contract_type_id = fields.Many2one('hr.contract.type', domain=lambda self: self._get_contract_type_domain(), default=lambda self: self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_indefiniteSalaryMth").id)
    l10n_ch_job_type = fields.Selection([
        ('highestCadre', 'Top Management'),
        ('middleCadre', 'Middle Management'),
        ('lowerCadre', 'Lower Management'),
        ('lowestCadre', 'Responsible for carrying out the work'),
        ('noCadre', 'Without management function'),
    ], default='noCadre', string="Job Type", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    wage_type = fields.Selection(selection_add=[("NoTimeConstraint", "No Time Constraint")],
                                 ondelete={"NoTimeConstraint": 'cascade'}, default="monthly")
    l10n_ch_laa_group = fields.Many2one("l10n.ch.accident.group", string="LAA Code", groups="hr.group_hr_user", tracking=True, domain='[("insurance_id.company_id", "=", company_id)]')
    laa_solution_number = fields.Selection(selection=[
        ('0', '0 - Not insured'),
        ('1', '1 - Occupational and Non-Occupational Insured, with deductions'),
        ('2', '2 - Occupational and Non-Occupational Insured, without deductions'),
        ('3', '3 - Only Occupational Insured')], default='1', groups="hr.group_hr_user", tracking=True)
    l10n_ch_lpp_withdrawal_reason = fields.Selection(selection=[('withdrawalCompany', "Withdrawal From Company"),
                                                                ('interruptionOfEmployment', 'Interruption Of Work'),
                                                                ('retirement', "Retirement"),
                                                                ('others', 'Others')], default="withdrawalCompany", string="Withdrawal Reason", help="""Specify here the entry in LPP reason.""", groups="hr.group_hr_user", tracking=True)
    l10n_ch_lpp_entry_reason = fields.Selection(selection=[('interruptionOfEmployment', 'Resuming Work After an Interruption'),
                                                           ('entryCompany', 'Entry In Company'),
                                                           ('others', 'Others')], string="Entry Reason", default="entryCompany", help="""Specify here the withdrawal from LPP reason.""", groups="hr.group_hr_user", tracking=True)
    l10n_ch_lpp_entry_valid_as_of = fields.Date("Entry Valid As Of", compute="_compute_l10n_ch_lpp_entry_valid_as_of", store=True, readonly=False, help="Please Provide the validity date of the last LPP Entry", groups="hr.group_hr_user")
    l10n_ch_lpp_withdrawal_valid_as_of = fields.Date("Withdrawal Valid As Of", compute="_compute_l10n_ch_lpp_withdrawal_valid_as_of", store=True, readonly=False, help="Please Provide the validity date of the last LPP Withdrawal", groups="hr.group_hr_user")
    l10n_ch_lpp_solutions = fields.Many2many('l10n.ch.lpp.insurance.line', string="LPP Codes", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_lpp_mutations = fields.One2many('l10n.ch.lpp.mutation', 'version_id', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    lpp_employee_amount = fields.Float(string="LPP Employee Contributions", groups="hr.group_hr_user", tracking=True)
    lpp_company_amount = fields.Float(string="LPP Company Contributions", groups="hr.group_hr_user", tracking=True)
    l10n_ch_14th_month = fields.Boolean(string="14th Month", groups="hr.group_hr_user", tracking=True)
    irregular_working_time = fields.Boolean(string="Irregular Working Time", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_weekly_hours = fields.Float(string="Weekly Hours", compute="_compute_l10n_ch_weekly_hours", store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_weekly_lessons = fields.Float(string="Weekly Lessons", groups="hr.group_hr_user", tracking=True)

    l10n_ch_thirteen_month = fields.Boolean(
        string="Has 13th Month", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_social_insurance_id = fields.Many2one(
        'l10n.ch.social.insurance', string="AVS/AC Insurance", groups="hr_payroll.group_hr_payroll_user", tracking=True, domain='[("company_id", "=", company_id)]')
    l10n_ch_lpp_insurance_id = fields.Many2one(
        'l10n.ch.lpp.insurance', string="LPP Insurance", groups="hr_payroll.group_hr_payroll_user", tracking=True, domain='[("company_id", "=", company_id)]')
    l10n_ch_accident_insurance_line_id = fields.Many2one(
        'l10n.ch.accident.insurance.line', string="LAA Insurance", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_additional_accident_insurance_line_ids = fields.Many2many(
        'l10n.ch.additional.accident.insurance.line', string="LAAC Insurances", groups="hr_payroll.group_hr_payroll_user", tracking=True, domain='[("insurance_id.company_id", "=", company_id)]')
    l10n_ch_sickness_insurance_line_ids = fields.Many2many(
        'l10n.ch.sickness.insurance.line', string="IJM Insurances", groups="hr_payroll.group_hr_payroll_user", tracking=True, domain='[("insurance_id.company_id", "=", company_id)]')
    l10n_ch_compensation_fund_id = fields.Many2one(
        'l10n.ch.compensation.fund', string="Family Compensation Fund", groups="hr_payroll.group_hr_payroll_user", tracking=True, domain='[("company_id", "=", company_id)]')
    l10n_ch_lesson_wage = fields.Float('Lesson Wage', tracking=True, help="Employee's gross wage by lesson.", groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_contractual_13th_month_rate = fields.Float("Contractual allowances for 13th/14th month", digits='Payroll Rate', default=8.3333, groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_location_unit_id = fields.Many2one("l10n.ch.location.unit", string="Workplace", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_avs_status = fields.Selection([
        ('youth', 'Youth'),
        ('exempted', 'Exempted'),
        ('retired', 'Retired'),
    ], string="AVS Special Status", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_yearly_holidays = fields.Integer(string="Yearly Holidays Count", default=20, groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_yearly_paid_public_holidays = fields.Integer(default=10, string="Yearly Paid Public Holidays Count", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_lpp_not_insured = fields.Boolean(string="Not LPP Insured", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_other_employers = fields.Boolean(groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_current_occupation_rate = fields.Float(string="Current Occupation rate", compute='_compute_l10n_ch_current_occupation_rate', inverse="_inverse_l10n_ch_current_occupation_rate", store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_other_employers_occupation_rate = fields.Float(compute="_compute_l10n_ch_other_employers_occupation_rate", store=True, groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_total_occupation_rate = fields.Float(string="Total occupation rate", compute="_compute_total_occupation_rate", groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_is_model = fields.Selection(string="IS Model", selection=[('monthly', 'Monthly'), ('yearly', 'Yearly')], default='monthly', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_is_predefined_category = fields.Char(string="IS Predefined Category", groups="hr_payroll.group_hr_payroll_user", help="Des barèmes fixes sont appliqués pour l'impôt à la source retenu sur les honoraires des administrateurs (art. 93 LIFD) et certaines participations de collaborateur (art. 97a LIFD). Pour ces impôts, aucun enfant n'est pris en compte et un seul taux en %% est appliqué. À cela s'ajoutent des catégories prédéfinies pour les annonces rectificatives et pour l'annonce des salaires bruts des frontaliers français pour lesquels l'accord spécial entre les cantons BE, BS, BL, JU, NE, SO, VD et VS et la France s'applique.", tracking=True)
    l10n_ch_monthly_effective_days = fields.Float(string="Monthly Effective Working Days", default=20, groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_contractual_holidays_rate = fields.Float(string="Holiday Compensation", compute="_compute_l10n_ch_contractual_holidays_rate", store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_contractual_public_holidays_rate = fields.Float(string="Public Holiday Compensation", compute="_compute_l10n_ch_contractual_public_holidays_rate", store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_contractual_vacation_pay = fields.Boolean(string="Pay Holiday Compensation each month", default=True, groups="hr_payroll.group_hr_payroll_user", help="""If unselected, vacation pay should be paid manually the moment the employee takes his vacation.""", tracking=True)
    l10n_ch_contractual_annual_wage = fields.Monetary(string="Contractual Annual Wage", default=0, groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_permanent_staff_public_admin = fields.Boolean("Permanent Staff for Public Administrations", groups="hr.group_hr_user", help="""
    A flag that allows for the clear identification of core personnel within public administrations.
    This flag will only be used by public administrations (municipalities, cities, districts, cantons, the Confederation, etc.) and churches.
    It will enable the distinction between core staff and various external mandates (such as exam experts, interpreters, etc.) and other engagements that are not part of the permanent workforce.
    """, tracking=True)
    l10n_ch_interim_worker = fields.Boolean(string="Interim Worker", groups="hr.group_hr_user", tracking=True)
    l10n_ch_contract_wage_ids = fields.One2many("l10n.ch.hr.contract.wage", "version_id", domain=[('date_start', '=', False)], copy=True, groups="hr_payroll.group_hr_payroll_user", tracking=True)
    one_time_wage_count = fields.Integer(compute="_compute_one_time_wage_count", groups="hr_payroll.group_hr_payroll_user")
    l10n_ch_has_monthly = fields.Boolean("Has Monthly Wage", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_has_hourly = fields.Boolean("Has Hourly Wage", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_ch_has_lesson = fields.Boolean("Has Lesson Wage", groups="hr_payroll.group_hr_payroll_user", tracking=True)

    @api.constrains('l10n_ch_municipality', 'l10n_ch_weekly_residence_municipality', 'private_country_id')
    def _check_swiss_address(self):
        for record in self:
            if record.private_country_id.code == 'CH':
                if record.l10n_ch_municipality and not record.l10n_ch_municipality.isdigit():
                    raise ValidationError(_('The residence Municipality must contain only numbers for Switzerland.'))
                if record.l10n_ch_weekly_residence_municipality and not record.l10n_ch_weekly_residence_municipality.isdigit():
                    raise ValidationError(_('The weekly residence municipality must contain only numbers for Switzerland.'))

    @api.constrains("l10n_ch_foreign_tax_id", "private_country_id")
    def _check_l10n_ch_foreign_tax_id(self):
        pattern = r"[A-Z]{6}[0-9]{2}(A|B|C|D|E|H|L|M|P|R|S|T)[0-9]{2}[A-Z]{1}[0-9]{3}[A-Z]{1}"
        for emp in self:
            if emp.private_country_id.code == "IT" and emp.l10n_ch_foreign_tax_id:
                match = re.match(pattern, emp.l10n_ch_foreign_tax_id)
                if not match:
                    raise ValidationError(_("Invalid Italian Tax-ID pattern"))

    @api.onchange('private_country_id')
    def _onchange_private_country_id(self):
        if self.private_country_id.code != 'CH':
            self.l10n_ch_canton = "EX"
            self.l10n_ch_municipality = False

    @api.onchange('l10n_ch_has_monthly')
    def _onchange_l10n_ch_has_monthly(self):
        if not self.l10n_ch_has_monthly:
            self.wage = 0

    @api.onchange('l10n_ch_has_hourly')
    def _onchange_l10n_ch_has_hourly(self):
        if not self.l10n_ch_has_hourly:
            self.hourly_wage = 0

    @api.onchange('l10n_ch_has_lesson')
    def _onchange_l10n_ch_has_lesson(self):
        if not self.l10n_ch_has_lesson:
            self.l10n_ch_lesson_wage = 0

    def _get_allowed_contract_type_ids(self):
        return (self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_indefiniteSalaryMth") +
                self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_indefiniteSalaryMthAWT") +
                self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_fixedSalaryMth") +
                self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_apprentice") +
                self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_internshipContract") +
                self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_indefiniteSalaryHrs") +
                self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_fixedSalaryHrs") +
                self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_indefiniteSalaryNoTimeConstraint") +
                self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_fixedSalaryNoTimeConstraint") +
                self.env.ref("l10n_ch_hr_payroll.l10n_ch_contract_type_administrativeBoard")).ids

    def generate_work_entries(self, date_start, date_stop, force=False):
        # Completely bypass work entry generation for Swiss Contracts
        swissdec_structure = self.env.ref("l10n_ch_hr_payroll.structure_type_employee_ch", raise_if_not_found=False)
        swiss_contracts = self.filtered(lambda c: c.structure_type_id.id == swissdec_structure.id)

        return super(HrVersion, self - swiss_contracts).generate_work_entries(date_start, date_stop, force)

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        swissdec_structure = self.env.ref("l10n_ch_hr_payroll.structure_type_employee_ch", raise_if_not_found=False)
        employees = contracts.filtered(lambda c: c.sudo().structure_type_id.id == swissdec_structure.id).mapped("employee_id")
        if not employees:
            return contracts
        employees._create_or_update_snapshot()
        return contracts

    def write(self, vals):
        res = super().write(vals)
        swissdec_structure = self.env.ref("l10n_ch_hr_payroll.structure_type_employee_ch", raise_if_not_found=False)
        employees = self.filtered(lambda c: c.sudo().structure_type_id.id == swissdec_structure.id).mapped("employee_id")
        if not employees:
            return res
        employees._create_or_update_snapshot()
        return res

    @api.depends("contract_date_end")
    def _compute_l10n_ch_lpp_withdrawal_valid_as_of(self):
        for contract in self:
            if contract.contract_date_end:
                contract.l10n_ch_lpp_withdrawal_valid_as_of = contract.contract_date_end
            else:
                contract.l10n_ch_lpp_withdrawal_valid_as_of = False

    @api.depends("contract_date_start")
    def _compute_l10n_ch_lpp_entry_valid_as_of(self):
        for contract in self:
            if contract.contract_date_start:
                contract.l10n_ch_lpp_entry_valid_as_of = contract.contract_date_start
            else:
                contract.l10n_ch_lpp_entry_valid_as_of = False

    @api.depends('l10n_ch_other_employment', 'l10n_ch_total_activity_type', 'l10n_ch_other_activity_percentage')
    def _compute_l10n_ch_other_employers_occupation_rate(self):
        for contract in self:
            if contract.l10n_ch_other_employment and contract.l10n_ch_total_activity_type == 'percentage':
                contract.l10n_ch_other_employers_occupation_rate = contract.l10n_ch_other_activity_percentage
            else:
                contract.l10n_ch_other_employers_occupation_rate = 0

    @api.depends('l10n_ch_location_unit_id')
    def _compute_l10n_ch_weekly_hours(self):
        for contract in self:
            if contract.l10n_ch_location_unit_id:
                contract.l10n_ch_weekly_hours = contract.l10n_ch_location_unit_id.weekly_hours

    @api.depends('l10n_ch_location_unit_id', 'l10n_ch_weekly_hours')
    def _compute_l10n_ch_current_occupation_rate(self):
        for contract in self:
            rate = 0
            if contract.l10n_ch_location_unit_id.weekly_hours > 0:
                rate += (contract.l10n_ch_weekly_hours / contract.l10n_ch_location_unit_id.weekly_hours) * 100
            if contract.l10n_ch_location_unit_id.weekly_lessons > 0:
                rate += (contract.l10n_ch_weekly_lessons / contract.l10n_ch_location_unit_id.weekly_lessons) * 100

            contract.l10n_ch_current_occupation_rate = rate

    def _inverse_l10n_ch_current_occupation_rate(self):
        for contract in self:
            if contract.l10n_ch_location_unit_id.weekly_hours > 0:
                contract.l10n_ch_weekly_hours = (contract.l10n_ch_location_unit_id.weekly_hours * contract.l10n_ch_current_occupation_rate) / 100

    @api.depends("l10n_ch_yearly_holidays")
    def _compute_l10n_ch_contractual_holidays_rate(self):
        for contract in self:
            contract.l10n_ch_contractual_holidays_rate = round((contract.l10n_ch_yearly_holidays / (260 - contract.l10n_ch_yearly_holidays)) * 100, 2)

    @api.depends("l10n_ch_yearly_paid_public_holidays")
    def _compute_l10n_ch_contractual_public_holidays_rate(self):
        for contract in self:
            contract.l10n_ch_contractual_public_holidays_rate = round((contract.l10n_ch_yearly_paid_public_holidays / (260 - contract.l10n_ch_yearly_paid_public_holidays)) * 100, 2)

    @api.depends('structure_type_id', 'contract_type_id')
    def _compute_wage_type(self):
        swissdec_structure = self.env.ref("l10n_ch_hr_payroll.structure_type_employee_ch")
        swissdec_contracts = self.filtered(lambda c: c.structure_type_id.id == swissdec_structure.id)
        for contract in swissdec_contracts:
            if contract.contract_type_id.code in ["indefiniteSalaryMth", "indefiniteSalaryMthAWT", "fixedSalaryMth", "apprentice", "internshipContract"]:
                contract.wage_type = "monthly"
            elif contract.contract_type_id.code in ["indefiniteSalaryHrs", "fixedSalaryHrs"]:
                contract.wage_type = "hourly"
            else:
                contract.wage_type = "NoTimeConstraint"

        super(HrVersion, self - swissdec_contracts)._compute_wage_type()

    @api.depends('l10n_ch_tax_scale', 'l10n_ch_tax_scale_type', 'l10n_ch_pre_defined_tax_scale', 'l10n_ch_open_tax_scale', "children", "l10n_ch_church_tax", 'l10n_ch_has_withholding_tax')
    def _compute_l10n_ch_tax_code(self):
        for employee in self:
            if employee.l10n_ch_has_withholding_tax:
                if employee.l10n_ch_tax_scale_type == "TaxAtSourceCode" and employee.l10n_ch_tax_scale:
                    employee.l10n_ch_tax_code = f"{employee.l10n_ch_tax_scale}{max(0, min(employee.children, 9))}{'Y' if employee.l10n_ch_church_tax else 'N'}"
                elif employee.l10n_ch_tax_scale_type == "CategoryPredefined" and employee.l10n_ch_pre_defined_tax_scale:
                    employee.l10n_ch_tax_code = employee.l10n_ch_pre_defined_tax_scale
                elif employee.l10n_ch_tax_scale_type == "CategoryOpen":
                    employee.l10n_ch_tax_code = employee.l10n_ch_open_tax_scale
                else:
                    employee.l10n_ch_tax_code = False
            else:
                employee.l10n_ch_tax_code = False

    @api.depends('l10n_ch_canton', 'l10n_ch_residence_type', 'l10n_ch_weekly_residence_canton', 'l10n_ch_has_withholding_tax', 'l10n_ch_location_unit_id')
    def _compute_l10n_ch_source_tax_canton(self):
        for employee in self:
            if employee.l10n_ch_has_withholding_tax:
                if employee.l10n_ch_canton != "EX":
                    employee.l10n_ch_source_tax_canton = employee.l10n_ch_canton
                else:
                    if employee.l10n_ch_residence_type == "Daily":
                        employee.l10n_ch_source_tax_canton = employee.l10n_ch_location_unit_id.canton
                    else:
                        employee.l10n_ch_source_tax_canton = employee.l10n_ch_weekly_residence_canton
            else:
                employee.l10n_ch_source_tax_canton = False

    @api.depends('l10n_ch_canton', 'l10n_ch_residence_type', 'l10n_ch_weekly_residence_municipality', 'l10n_ch_has_withholding_tax')
    def _compute_l10n_ch_source_tax_municipality(self):
        for employee in self:
            if employee.l10n_ch_has_withholding_tax:
                if employee.l10n_ch_canton != "EX":
                    employee.l10n_ch_source_tax_municipality = employee.l10n_ch_municipality
                else:
                    if employee.l10n_ch_residence_type == "Daily":
                        employee.l10n_ch_source_tax_municipality = employee.l10n_ch_location_unit_id.municipality
                    else:
                        employee.l10n_ch_source_tax_municipality = employee.l10n_ch_weekly_residence_municipality
            else:
                employee.l10n_ch_source_tax_municipality = False

    def action_view_wages(self):
        self.ensure_one()
        action = self.env.ref('l10n_ch_hr_payroll.action_l10n_ch_hr_contract_wage').read()[0]
        action['domain'] = [('version_id', '=', self.id),
                            ('date_start', '!=', False)]
        action['context'] = {
            'default_version_id': self.id,
        }

        return action

    def _compute_one_time_wage_count(self):
        grouped_wages = dict(self.env['l10n.ch.hr.contract.wage']._read_group(domain=[('version_id', 'in', self.ids),
                                                                 ('date_start', '!=', False)],
                                                         groupby=['version_id'], aggregates=['version_id:count']))
        for contract in self:
            contract.one_time_wage_count = grouped_wages.get(contract, 0)

    @api.depends('private_zip')
    def _compute_autocomplete_private_address(self):
        ZIP_DATA = self.env['hr.rule.parameter']._get_parameter_from_code("l10n_ch_bfs_municipalities", fields.Date.today(), raise_if_not_found=False)
        if ZIP_DATA:
            for record in self:
                if record.private_zip:
                    data = ZIP_DATA.get(record.private_zip)
                    if data:
                        record.private_city = data[0]
                        record.l10n_ch_municipality = data[1]
                        record.l10n_ch_canton = data[2]

    @api.depends('l10n_ch_weekly_residence_address_zip')
    def _compute_weekly_residence_autocomplete(self):
        ZIP_DATA = self.env['hr.rule.parameter']._get_parameter_from_code("l10n_ch_bfs_municipalities", fields.Date.today(), raise_if_not_found=False)
        if ZIP_DATA:
            for record in self:
                if record.l10n_ch_weekly_residence_address_zip:
                    data = ZIP_DATA.get(record.l10n_ch_weekly_residence_address_zip)
                    if data:
                        record.l10n_ch_weekly_residence_address_city = data[0]
                        record.l10n_ch_weekly_residence_municipality = data[1]
                        record.l10n_ch_weekly_residence_canton = data[2]

    @api.depends('l10n_ch_other_employers_occupation_rate', 'l10n_ch_current_occupation_rate')
    def _compute_total_occupation_rate(self):
        for contract in self:
            contract.l10n_ch_total_occupation_rate = contract.l10n_ch_other_employers_occupation_rate + contract.l10n_ch_current_occupation_rate

    def _get_marital_status_selection(self):
        if self.env.company.country_id.code != "CH":
            return super()._get_marital_status_selection()
        return super()._get_marital_status_selection() + [
            ("separated", _("Separated")),
            ("registered_partnership", _("Registered Partnership")),
            ("partnership_dissolved_by_law", _("Partnership Dissolved By Law")),
            ("partnership_dissolved_by_death", _("Partnership Dissolved By Death")),
            ("partnership_dissolved_by_declaration_of_lost", _("Partnership Dissolved By Declaration of Lost")),
        ]

    @api.constrains('l10n_ch_spouse_sv_as_number')
    def _check_l10n_ch_spouse_sv_as_number(self):
        for employee in self:
            if not employee.l10n_ch_spouse_sv_as_number:
                continue
            self.env['hr.employee']._validate_sv_as_number(employee.l10n_ch_spouse_sv_as_number)

    def _get_l10n_ch_declaration_marital(self):
        self.ensure_one()
        mapped_marital = {
            'unknown': "unknown",
            'single': 'single',
            'married': 'married',
            'widower': 'widowed',
            'divorced': 'divorced',
            'separated': 'separated',
            'registered_partnership': 'registeredPartnership',
            'partnership_dissolved_by_law': 'partnershipDissolvedByLaw',
            'partnership_dissolved_by_death': 'partnershipDissolvedByDeath',
            'partnership_dissolved_by_declaration_of_lost': 'partnershipDissolvedByDeclarationOfLost',
        }
        if self.marital not in mapped_marital:
            raise UserError(_('Invalid marital status for employee %s', self.name))
        return mapped_marital[self.marital]

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelist_fields = super()._get_whitelist_fields_from_template()
        if self.env.company.country_id.code == "CH":
            whitelist_fields += [
                "l10n_ch_accident_insurance_line_id",
                "l10n_ch_additional_accident_insurance_line_ids",
                "l10n_ch_avs_status",
                "l10n_ch_compensation_fund_id",
                "l10n_ch_contractual_13th_month_rate",
                "l10n_ch_is_model",
                "l10n_ch_is_predefined_category",
                "l10n_ch_job_type",
                "l10n_ch_lesson_wage",
                "l10n_ch_location_unit_id",
                "l10n_ch_lpp_insurance_id",
                "l10n_ch_lpp_not_insured",
                "l10n_ch_monthly_effective_days",
                "l10n_ch_other_employers",
                "l10n_ch_other_employers_occupation_rate",
                "l10n_ch_sickness_insurance_line_ids",
                "l10n_ch_social_insurance_id",
                "l10n_ch_thirteen_month",
                "l10n_ch_total_occupation_rate",
                "l10n_ch_yearly_holidays",
                "l10n_ch_yearly_paid_public_holidays",
            ]
        return whitelist_fields
