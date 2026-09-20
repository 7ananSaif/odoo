# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_jo_standard(self, companies):
        account_codes = [
            '200101',  # Payables
            '200307',  # Employee Income Tax
            '200308',  # Social Security Payable
            '200502',  # Leave Days Provision
            '200503',  # End of Service Provision
            '500202',  # End Of Service Indemnity
            '500301',  # Basic Salary
            '500302',  # Housing Allowance
            '500303',  # Transportation Allowance
            '500305',  # Leave Salary
            '500308',  # Staff Other Allowances
            '500310',  # Salary Deductions
            '500311',  # Social Security Expenses
        ]
        default_account = '200101'
        rules_mapping = defaultdict(dict)

        # ================================================ #
        #           JO Employee Payroll Structure          #
        # ================================================ #

        basic_rule = self.env['hr.salary.rule'].search([
            ('struct_id', '=', self.env.ref('l10n_jo_hr_payroll.hr_payroll_structure_jo_employee_salary').id),
            ('code', '=', 'BASIC'),
        ], limit=1)
        rules_mapping[basic_rule]['debit'] = '500301'

        house_rule = self.env.ref('l10n_jo_hr_payroll.jordan_housing_allowance_salary_rule')
        rules_mapping[house_rule]['debit'] = '500302'

        transportation_rule = self.env.ref('l10n_jo_hr_payroll.jordan_transportation_allowance_salary_rule')
        rules_mapping[transportation_rule]['debit'] = '500303'

        other_allowances_rule = self.env.ref('l10n_jo_hr_payroll.jordan_other_allowances_salary_rule')
        rules_mapping[other_allowances_rule]['debit'] = '500308'

        sse_deduction_rule = self.env.ref('l10n_jo_hr_payroll.jordan_sse_deduction')
        rules_mapping[sse_deduction_rule]['debit'] = '200308'

        ssc_contribution_rule = self.env.ref('l10n_jo_hr_payroll.jordan_ssc_contribution')
        rules_mapping[ssc_contribution_rule]['debit'] = '500311'
        rules_mapping[ssc_contribution_rule]['credit'] = '200308'

        sick_leave_deduction_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_sick_leave_unpaid')
        rules_mapping[sick_leave_deduction_rule]['debit'] = '500310'

        rest_days_overtime_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_rest_days_overtime')
        rules_mapping[rest_days_overtime_rule]['debit'] = '500308'

        week_days_overtime_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_week_days_overtime')
        rules_mapping[week_days_overtime_rule]['debit'] = '500308'

        end_service_provision_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_end_of_service_provision')
        rules_mapping[end_service_provision_rule]['debit'] = '500202'
        rules_mapping[end_service_provision_rule]['credit'] = '200503'

        annual_leave_provision_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_Annual_Leave_provision')
        rules_mapping[annual_leave_provision_rule]['debit'] = '500305'
        rules_mapping[annual_leave_provision_rule]['credit'] = '200502'

        tax_bracket_total_rule = self.env.ref('l10n_jo_hr_payroll.jordan_tax_tax_bracket_total')
        rules_mapping[tax_bracket_total_rule]['debit'] = '200307'

        end_service_benefit_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_end_of_service_benefit')
        rules_mapping[end_service_benefit_rule]['debit'] = '200503'

        remaining_leave_compensation_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_remaining_leave_compensation')
        rules_mapping[remaining_leave_compensation_rule]['debit'] = '200502'

        end_service_tax_ded_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_end_of_service_tax_deduction')
        rules_mapping[end_service_tax_ded_rule]['debit'] = '500310'

        assignment_of_salary_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_assignment_of_salary_rule')
        rules_mapping[assignment_of_salary_rule]['debit'] = '500310'

        child_support_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_child_support')
        rules_mapping[child_support_rule]['debit'] = '500310'

        deduction_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_deduction_salary_rule')
        rules_mapping[deduction_rule]['debit'] = '500310'

        reimbursement_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_reimbursement_salary_rule')
        rules_mapping[reimbursement_rule]['debit'] = '200101'

        net_rule = self.env['hr.salary.rule'].search([
            ('struct_id', '=', self.env.ref('l10n_jo_hr_payroll.hr_payroll_structure_jo_employee_salary').id),
            ('code', '=', 'NET'),
        ], limit=1)
        rules_mapping[net_rule]['credit'] = '200101'

        self._configure_payroll_account(
            companies,
            "JO",
            account_codes=account_codes,
            rules_mapping=rules_mapping,
            default_account=default_account)
