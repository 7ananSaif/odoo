# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_lu_index_on_contract_signature = fields.Float(
        string='Index on Contract Signature (LU)', readonly=True, compute='_compute_indexed_wage', groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_indexed_wage = fields.Monetary(string='Indexed Wage (LU)', compute='_compute_indexed_wage', groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_current_index = fields.Float(string='Current Index (LU)', compute='_compute_indexed_wage', groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_meal_voucher_amount = fields.Monetary(string='Meal Vouchers (LU)', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_meal_voucher_employer_cost = fields.Monetary(
        string='Meal Voucher Employer Cost (LU)', compute='_compute_l10n_lu_meal_voucher_employer_cost', groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_meal_voucher_employee_computation = fields.Selection(
        selection=[('removed_from_net', 'Removed From Net'),
        ('consider_as_bik', 'Consider as Benefit in Kind')],
        string="Employee Computation (LU)",
        required=True,
        groups="hr_payroll.group_hr_payroll_user",
        default='removed_from_net',
        tracking=True,
    )
    l10n_lu_bik_meal_voucher_exceeding_amount = fields.Monetary(
        string='BIK Meal Voucher Exceeding Amount (LU)', groups="hr_payroll.group_hr_payroll_user",
        compute="_compute_l10n_lu_meal_voucher_employer_cost")
    l10n_lu_bik_vehicle = fields.Monetary(string='BIK Vehicle (LU)', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_bik_vehicle_vat_included = fields.Boolean(string='BIK Vehicle VAT Included (LU)', default=True, groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_bik_other_benefits = fields.Monetary(string='Others', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_alw_vehicle = fields.Monetary(string='Allowance Vehicle (LU)', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_tax_id_number = fields.Char(
        string="Tax Identification Number",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True)
    l10n_lu_tax_classification = fields.Selection([
        ('1', '1'),
        ('1a', '1a'),
        ('2', '2'),
        ('without', 'Without')],
        string="Tax Classification",
        default='1', required=True,
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_tax_rate_no_classification = fields.Float(
        string="Tax Rate",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_deduction_fd_daily = fields.Monetary(
        string="FD",
        help="Travel Expenses",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_deduction_fd_monthly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_fd",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_deduction_fd_yearly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_fd",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_deduction_ac_ae_daily = fields.Monetary(
        string="AC/AE",
        help="Spousal Deduction / Extra-professional Deduction",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_deduction_ac_ae_monthly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_ac_ae",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_deduction_ac_ae_yearly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_ac_ae",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_deduction_ce_daily = fields.Monetary(
        string="CE",
        help="Extraordinary Charges",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_deduction_ce_monthly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_ce",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_deduction_ce_yearly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_ce",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_deduction_ds_daily = fields.Monetary(
        string="DS",
        help="Special Expenses",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_deduction_ds_monthly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_ds",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_deduction_ds_yearly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_ds",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_deduction_fo_daily = fields.Monetary(
        string="FO",
        help="Obtaining Fees",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_deduction_fo_monthly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_fo",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_deduction_fo_yearly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_fo",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_deduction_amd_daily = fields.Monetary(
        string="AMD",
        help="Sustainable Mobility Deduction",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_deduction_amd_monthly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_amd",
        groups="hr.group_hr_user")
    l10n_lu_deduction_amd_yearly = fields.Monetary(
        compute="_compute_l10n_lu_deduction_amd",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_package_ffo_daily = fields.Monetary(
        string="FFO",
        help="Obtaining Fees Package",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_package_ffo_monthly = fields.Monetary(
        compute="_compute_l10n_lu_package_ffo",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_package_ffo_yearly = fields.Monetary(
        compute="_compute_l10n_lu_package_ffo",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_package_fds_daily = fields.Monetary(
        string="FDS",
        help="Special Expenses Package",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_package_fds_monthly = fields.Monetary(
        compute="_compute_l10n_lu_package_fds",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_package_fds_yearly = fields.Monetary(
        compute="_compute_l10n_lu_package_fds",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_lu_tax_credit_cis = fields.Boolean(
        string="CIS",
        help="Employee Tax Credit",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_tax_credit_cip = fields.Boolean(
        string="CIP",
        help="Retiree Tax Credit",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lu_tax_credit_cim = fields.Boolean(
        string="CIM",
        help="Single-parent Tax Credit",
        groups="hr_payroll.group_hr_payroll_user", tracking=True)

    _check_meal_voucher_amount = models.Constraint(
        'check(l10n_lu_meal_voucher_amount = 0 OR l10n_lu_meal_voucher_amount >= 2.8)',
        'The meal voucher amount can be zero for no meal voucher benefit or more than or equal to 2.8 euros'
    )

    @api.depends('wage')
    def _compute_indexed_wage(self):
        for version in self:
            version.l10n_lu_index_on_contract_signature = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_index', date=version.date_start, raise_if_not_found=False)
            version.l10n_lu_current_index = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_index', raise_if_not_found=False)
            if version.l10n_lu_index_on_contract_signature and version.l10n_lu_current_index:
                version.l10n_lu_indexed_wage = (
                    version.wage if version.wage_type == 'monthly' else version.hourly_wage
                ) / version.l10n_lu_index_on_contract_signature * version.l10n_lu_current_index
            else:
                version.l10n_lu_indexed_wage = version.wage

    @api.depends('l10n_lu_meal_voucher_amount')
    def _compute_l10n_lu_meal_voucher_employer_cost(self):
        meal_voucher_max_value = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_meal_voucher_max_value', raise_if_not_found=False)
        if not meal_voucher_max_value:
            self.l10n_lu_meal_voucher_employer_cost = 0
            self.l10n_lu_bik_meal_voucher_exceeding_amount = 0
            return
        # The employee always pays 2.8€ per meal voucher.
        # The employer contributes for the rest up to a maximum amount.
        for version in self:
            if version.l10n_lu_meal_voucher_amount and version.l10n_lu_meal_voucher_amount > 2.8:
                contract_employer_contribution = version.l10n_lu_meal_voucher_amount - 2.8
                maximum_employer_contribution = meal_voucher_max_value - 2.8
                version.l10n_lu_meal_voucher_employer_cost = min(contract_employer_contribution, maximum_employer_contribution)
            else:
                version.l10n_lu_meal_voucher_employer_cost = 0

            version.l10n_lu_bik_meal_voucher_exceeding_amount = max(0, version.l10n_lu_meal_voucher_amount - meal_voucher_max_value)

    @api.depends('l10n_lu_deduction_fd_daily')
    def _compute_l10n_lu_deduction_fd(self):
        days_per_month = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_days_per_month', raise_if_not_found=False) or 25
        for version in self:
            version.l10n_lu_deduction_fd_monthly = version.l10n_lu_deduction_fd_daily * days_per_month
            version.l10n_lu_deduction_fd_yearly = version.l10n_lu_deduction_fd_monthly * 12

    @api.depends('l10n_lu_deduction_ac_ae_daily')
    def _compute_l10n_lu_deduction_ac_ae(self):
        days_per_month = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_days_per_month', raise_if_not_found=False) or 25
        for version in self:
            version.l10n_lu_deduction_ac_ae_monthly = version.l10n_lu_deduction_ac_ae_daily * days_per_month
            version.l10n_lu_deduction_ac_ae_yearly = version.l10n_lu_deduction_ac_ae_monthly * 12

    @api.depends('l10n_lu_deduction_ce_daily')
    def _compute_l10n_lu_deduction_ce(self):
        days_per_month = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_days_per_month', raise_if_not_found=False) or 25
        for version in self:
            version.l10n_lu_deduction_ce_monthly = version.l10n_lu_deduction_ce_daily * days_per_month
            version.l10n_lu_deduction_ce_yearly = version.l10n_lu_deduction_ce_monthly * 12

    @api.depends('l10n_lu_deduction_ds_daily')
    def _compute_l10n_lu_deduction_ds(self):
        days_per_month = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_days_per_month', raise_if_not_found=False) or 25
        for version in self:
            version.l10n_lu_deduction_ds_monthly = version.l10n_lu_deduction_ds_daily * days_per_month
            version.l10n_lu_deduction_ds_yearly = version.l10n_lu_deduction_ds_monthly * 12

    @api.depends('l10n_lu_deduction_fo_daily')
    def _compute_l10n_lu_deduction_fo(self):
        days_per_month = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_days_per_month', raise_if_not_found=False) or 25
        for version in self:
            version.l10n_lu_deduction_fo_monthly = version.l10n_lu_deduction_fo_daily * days_per_month
            version.l10n_lu_deduction_fo_yearly = version.l10n_lu_deduction_fo_monthly * 12

    @api.depends('l10n_lu_deduction_amd_daily')
    def _compute_l10n_lu_deduction_amd(self):
        days_per_month = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_days_per_month', raise_if_not_found=False) or 25
        for version in self:
            version.l10n_lu_deduction_amd_monthly = version.l10n_lu_deduction_amd_daily * days_per_month
            version.l10n_lu_deduction_amd_yearly = version.l10n_lu_deduction_amd_monthly * 12

    @api.depends('l10n_lu_package_ffo_daily')
    def _compute_l10n_lu_package_ffo(self):
        days_per_month = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_days_per_month', raise_if_not_found=False) or 25
        for version in self:
            version.l10n_lu_package_ffo_monthly = version.l10n_lu_package_ffo_daily * days_per_month
            version.l10n_lu_package_ffo_yearly = version.l10n_lu_package_ffo_monthly * 12

    @api.depends('l10n_lu_package_fds_daily')
    def _compute_l10n_lu_package_fds(self):
        days_per_month = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_lu_days_per_month', raise_if_not_found=False) or 25
        for version in self:
            version.l10n_lu_package_fds_monthly = version.l10n_lu_package_fds_daily * days_per_month
            version.l10n_lu_package_fds_yearly = version.l10n_lu_package_fds_monthly * 12

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "LU":
            whitelisted_fields += [
                "l10n_lu_alw_vehicle",
                "l10n_lu_bik_other_benefits",
                "l10n_lu_bik_vehicle",
                "l10n_lu_bik_vehicle_vat_included",
                "l10n_lu_current_index",
                "l10n_lu_index_on_contract_signature",
                "l10n_lu_indexed_wage",
                "l10n_lu_meal_voucher_amount",
                "l10n_lu_meal_voucher_employee_computation",
                "l10n_lu_meal_voucher_employer_cost",
            ]
        return whitelisted_fields
