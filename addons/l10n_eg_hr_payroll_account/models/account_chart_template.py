# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_eg(self, companies):
        account_codes = [
            '201002',  # Payables
            '201026',  # Social Contribution - Payable to authorities,
            '201027',  # Income Tax payable to Authority - Deducted from employee's salaries
            '202001',  # End of Service Provision,
            '400003',  # Basic Salary
            '400005',  # Transportation Allowance
            '400008',  # End of Service Indemnity
            '400012',  # Staff Other Allowances
            '400078',  # Social Contibution - Company portion expense
            '400004',  # Housing Allowence
            '400080',  # Salary Deductions,
            '400007',  # Leave Salary,
            '201006',  # Leave Days Provision,
        ]
        default_account = '400003'
        rules_mapping = defaultdict(dict)

        rule = self.env['hr.salary.rule'].search([
            ('struct_id', '=', self.env.ref('l10n_eg_hr_payroll.hr_payroll_structure_eg_employee_salary').id),
            ('code', '=', 'BASIC')
        ], limit=1)
        rules_mapping[rule]['debit'] = '400003'

        deduction_rules = [
            self.env.ref('l10n_eg_hr_payroll.10n_eg_hr_payroll_structure_eg_employee_salary_out_of_contract_days_deduction'),
            self.env.ref('l10n_eg_hr_payroll.10n_eg_hr_payroll_structure_eg_employee_salary_unpaid_leave_decuction'),
            self.env.ref('l10n_eg_hr_payroll.10n_eg_hr_payroll_structure_eg_employee_salary_sick_leave_deduction_75'),
            self.env.ref('l10n_eg_hr_payroll.10n_eg_hr_payroll_structure_eg_employee_salary_sick_leave_unpaid_deduction'),
            self.env.ref('l10n_eg_hr_payroll.l10n_eg_hr_payroll_structure_eg_employee_salary_deduction_salary_rule'),
        ]
        for rule in deduction_rules:
            rules_mapping[rule]['debit'] = '400080'

        other_allowance_rules = [
            self.env.ref('l10n_eg_hr_payroll.egypt_other_allowances_salary_rule'),
            self.env.ref('l10n_eg_hr_payroll.10n_eg_hr_payroll_structure_eg_employee_salary_overtime_weekdays_daytime'),
            self.env.ref('l10n_eg_hr_payroll.10n_eg_hr_payroll_structure_eg_employee_salary_overtime_weekdays_nighttime'),
            self.env.ref('l10n_eg_hr_payroll.10n_eg_hr_payroll_structure_eg_employee_salary_overtime_weekdays_public_holidays'),
            self.env.ref('l10n_eg_hr_payroll.l10n_eg_hr_payroll_structure_eg_employee_salary_attachment_of_salary_rule'),
            self.env.ref('l10n_eg_hr_payroll.l10n_eg_hr_payroll_structure_eg_employee_salary_assignment_of_salary_rule'),
            self.env.ref('l10n_eg_hr_payroll.l10n_eg_hr_payroll_structure_eg_employee_salary_child_support'),
        ]
        for rule in other_allowance_rules:
            rules_mapping[rule]['debit'] = '400012'

        rule = self.env.ref('l10n_eg_hr_payroll.10n_eg_hr_payroll_structure_eg_employee_salary_housing_allowance')
        rules_mapping[rule]['debit'] = '400004'

        rule = self.env.ref('l10n_eg_hr_payroll.egypt_housing_allowance_salary_rule')
        rules_mapping[rule]['debit'] = '400005'

        rule = self.env.ref('l10n_eg_hr_payroll.egypt_social_insurance_contribution_company')
        rules_mapping[rule]['debit'] = '400078'
        rules_mapping[rule]['credit'] = '201026'

        rule = self.env.ref('l10n_eg_hr_payroll.egypt_social_insurance_contribution_employee')
        rules_mapping[rule]['debit'] = '201026'

        rule = self.env.ref('l10n_eg_hr_payroll.egypt_end_of_service_provision_salary_rule')
        rules_mapping[rule]['debit'] = '400008'
        rules_mapping[rule]['credit'] = '202001'

        rule = self.env.ref('l10n_eg_hr_payroll.l10n_eg_salary_rule_annual_leave_provision')
        rules_mapping[rule]['debit'] = '400007'
        rules_mapping[rule]['credit'] = '201006'

        rule = self.env.ref('l10n_eg_hr_payroll.l10n_eg_salary_rule_annual_leave_compensation')
        rules_mapping[rule]['debit'] = '400007'

        rule = self.env.ref('l10n_eg_hr_payroll.egypt_end_of_service_benefit_salary_rule')
        rules_mapping[rule]['debit'] = '202001'

        rule = self.env.ref('l10n_eg_hr_payroll.egypt_tax_bracket_total')
        rules_mapping[rule]['debit'] = '201027'

        rule = self.env.ref('l10n_eg_hr_payroll.l10n_eg_hr_payroll_structure_eg_employee_salary_deduction_salary_rule')
        rules_mapping[rule]['debit'] = '400080'

        rule = self.env.ref('l10n_eg_hr_payroll.l10n_eg_hr_payroll_structure_eg_employee_salary_reimbursement_salary_rule')
        rules_mapping[rule]['debit'] = '201002'

        rule = self.env.ref('l10n_eg_hr_payroll.l10n_eg_hr_payroll_structure_eg_employee_salary_expenses_reimbursement')
        rules_mapping[rule]['debit'] = '201002'

        rule = self.env['hr.salary.rule'].search([
            ('struct_id', '=', self.env.ref('l10n_eg_hr_payroll.hr_payroll_structure_eg_employee_salary').id),
            ('code', '=', 'NET')
        ], limit=1)
        rules_mapping[rule]['credit'] = '201002'

        # ================================================ #
        #           EG Employee Payroll Structure          #
        # ================================================ #

        self._configure_payroll_account(
            companies,
            "EG",
            account_codes=account_codes,
            rules_mapping=rules_mapping,
            default_account=default_account)
