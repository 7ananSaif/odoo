# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_sa(self, companies):
        account_codes = [
            '106012',  # Prepaid Employee Expenses
            '201002',  # Payables
            '201006',  # Leave Days Provision
            '201016',  # Accrued Others
            '201022',  # GOSI Employee Payable
            '202001',  # End of Service Provision
            '400003',  # Basic Salary
            '400004',  # Housing Allowance
            '400005',  # Transportation Allowance
            '400007',  # Leave Salary
            '400008',  # End of Service Indemnity
            '400009',  # Medical Insurance
            '400010',  # Life insurance
            '400012',  # Staff Other Allowances
            '400014',  # Visa Expenses
            '400074',  # Salary Deductions
        ]
        default_account = '201002'
        rules_mapping = defaultdict(dict)

        # ================================================ #
        #          KSA Employee Payroll Structure          #
        # ================================================ #

        basic_rule = self.env['hr.salary.rule'].search([
            ('struct_id', '=', self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id),
            ('code', '=', 'BASIC')
        ], limit=1)
        rules_mapping[basic_rule]['debit'] = '400003'

        house_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_housing_allowance_salary_rule')
        rules_mapping[house_rule]['debit'] = '400004'

        transport_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_transportation_allowance_salary_rule')
        rules_mapping[transport_rule]['debit'] = '400005'

        other_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_other_allowances_salary_rule')
        rules_mapping[other_rule]['debit'] = '400012'

        out_of_contract_days_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_out_of_contract_days')
        rules_mapping[out_of_contract_days_rule]['debit'] = '400074'

        social_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_social_insurance_contribution')
        rules_mapping[social_rule]['debit'] = '400010'
        rules_mapping[social_rule]['credit'] = '201022'

        social_insurance_employee_contribution_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_social_insurance_employee_contribution')
        rules_mapping[social_insurance_employee_contribution_rule]['debit'] = '201022'

        expenses_reimbursement_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_expenses_reimbursement')
        rules_mapping[expenses_reimbursement_rule]['debit'] = '201002'

        unpaid_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_unpaid_leave')
        rules_mapping[unpaid_rule]['debit'] = '400074'

        sick_leave_unpaid_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_sick_leave_unpaid')
        rules_mapping[sick_leave_unpaid_rule]['debit'] = '400074'

        sick_leave_75_paid_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_deduction_sick_leave_75_paid')
        rules_mapping[sick_leave_75_paid_rule]['debit'] = '400074'

        overtime_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_overtime')
        rules_mapping[overtime_rule]['debit'] = '400012'

        provision_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_end_of_service_provision_salary_rule')
        rules_mapping[provision_rule]['debit'] = '400008'
        rules_mapping[provision_rule]['credit'] = '202001'

        annual_leave_provision_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_annual_leave_provision')
        rules_mapping[annual_leave_provision_rule]['debit'] = '400007'
        rules_mapping[annual_leave_provision_rule]['credit'] = '201006'

        remaining_leave_days_compensation_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_remaining_leave_days_compensation')
        rules_mapping[remaining_leave_days_compensation_rule]['debit'] = '201006'

        end_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_end_of_service_salary_rule')
        rules_mapping[end_rule]['debit'] = '202001'

        clause_77_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_end_of_service_clause_77_salary_rule')
        rules_mapping[clause_77_rule]['debit'] = '400012'

        exit_re_entry_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_exit_re_entry')
        rules_mapping[exit_re_entry_rule]['debit'] = '400012'

        medical_insurance_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_medical_insureance')
        rules_mapping[medical_insurance_rule]['debit'] = '400009'
        rules_mapping[medical_insurance_rule]['credit'] = '106012'

        iqama_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_iqama')
        rules_mapping[iqama_rule]['debit'] = '400014'
        rules_mapping[iqama_rule]['credit'] = '106012'

        work_permit_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_work_permit')
        rules_mapping[work_permit_rule]['debit'] = '400014'
        rules_mapping[work_permit_rule]['credit'] = '106012'

        attachment_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_attachment_of_salary_rule')
        rules_mapping[attachment_rule]['debit'] = '400074'

        assignment_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_assignment_of_salary_rule')
        rules_mapping[assignment_rule]['debit'] = '400074'

        child_support_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_child_support')
        rules_mapping[child_support_rule]['debit'] = '400012'

        deduction_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_deduction_salary_rule')
        rules_mapping[deduction_rule]['debit'] = '400074'

        reimbursement_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_reimbursement_salary_rule')
        rules_mapping[reimbursement_rule]['debit'] = '201002'

        loan_deduction_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_loan_deduction')
        rules_mapping[loan_deduction_rule]['debit'] = '400074'

        salary_advance_recovery_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_salary_advance_recovery')
        rules_mapping[salary_advance_recovery_rule]['debit'] = '400074'

        net_rule = self.env['hr.salary.rule'].search([
            ('struct_id', '=', self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id),
            ('code', '=', 'NET')
        ], limit=1)
        rules_mapping[net_rule]['credit'] = '201002'

        self._configure_payroll_account(
            companies,
            "SA",
            account_codes=account_codes,
            rules_mapping=rules_mapping,
            default_account=default_account)
