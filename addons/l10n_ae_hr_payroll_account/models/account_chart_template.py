# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_ae(self, companies):
        account_codes = [
            '201002',  # Payables
            '202001',  # End of Service Provision
            '400003',  # Basic Salary
            '400004',  # Housing Allowance
            '400005',  # Transportation Allowance
            '400008',  # End of Service Indemnity
            '400012',  # Staff Other Allowances
            '400074',  # Salary Deductions
            '400007',  # Leave Salary
            '400073',  # Social Insurance Expense
            '201021',  # Social Insurance Payable
            '201022',  # DEWS Payable
            '201006',  # Leave Days Provision
        ]
        default_account = '400003'
        rules_mapping = defaultdict(dict)

        # ================================================ #
        #          UAE Employee Payroll Structure          #
        # ================================================ #

        basic_rule = self.env['hr.salary.rule'].search([
            ('struct_id', '=', self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure').id),
            ('code', '=', 'BASIC')
        ], limit=1)
        rules_mapping[basic_rule]['debit'] = '400003'

        other_allowance_rule = [
            # United Arab Emirates: Regular Pay Structure
            self.env.ref('l10n_ae_hr_payroll.uae_salary_rule_input_housing_allowance'),
            self.env.ref('l10n_ae_hr_payroll.uae_salary_rule_conveyance_allowance'),
            self.env.ref('l10n_ae_hr_payroll.uae_salary_rule_medical_allowance'),
            self.env.ref('l10n_ae_hr_payroll.uae_salary_rule_annual_passage_allowance'),
            self.env.ref('l10n_ae_hr_payroll.uae_salary_rule_overtime_allowance'),
            self.env.ref('l10n_ae_hr_payroll.uae_salary_rule_other_allowance'),
            self.env.ref('l10n_ae_hr_payroll.uae_salary_rule_leave_encashment'),
            self.env.ref('l10n_ae_hr_payroll.uae_salary_arrears_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.uae_other_earnings_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.uae_bonus_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.uae_airfare_allowance_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.uae_salary_rule_other_allowance'),
            self.env.ref('l10n_ae_hr_payroll.l10n_ae_hr_payroll_uae_employee_payroll_structure_child_support'),
            # United Arab Emirates: Instant Pay Structure
            self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_allowance'),
            self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_commission'),
            self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_salary_advance'),
            self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_loan_advance'),

        ]
        for rule in other_allowance_rule:
            rules_mapping[rule]['debit'] = '400012'

        deduction_rule = [
            # United Arab Emirates: Regular Pay Structure
            self.env.ref('l10n_ae_hr_payroll.uae_salary_deduction_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.uae_other_deduction_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.uae_sick_leave_50_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.uae_sick_leave_0_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.uae_unpaid_leave_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.uae_out_of_contract_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_employee_payroll_structure_advance_recovery'),
            self.env.ref('l10n_ae_hr_payroll.l10n_ae_hr_payroll_uae_employee_payroll_structure_attachment_of_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.l10n_ae_hr_payroll_uae_employee_payroll_structure_assignment_of_salary_rule'),
            self.env.ref('l10n_ae_hr_payroll.l10n_ae_hr_payroll_uae_employee_payroll_structure_deduction_salary_rule'),
            # United Arab Emirates: Instant Pay Structure
            self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_deduction'),
        ]
        for rule in deduction_rule:
            rules_mapping[rule]['debit'] = '400074'

        house_rule = self.env.ref('l10n_ae_hr_payroll.uae_housing_allowance_salary_rule')
        rules_mapping[house_rule]['debit'] = '400004'

        transport_rule = self.env.ref('l10n_ae_hr_payroll.uae_transportation_allowance_salary_rule')
        rules_mapping[transport_rule]['debit'] = '400005'

        other_rule = self.env.ref('l10n_ae_hr_payroll.uae_other_allowances_salary_rule')
        rules_mapping[other_rule]['debit'] = '400012'

        end_rule = self.env.ref('l10n_ae_hr_payroll.uae_end_of_service_salary_rule')
        rules_mapping[end_rule]['debit'] = '202001'

        provision_rule = self.env.ref('l10n_ae_hr_payroll.uae_end_of_service_provision_salary_rule')
        rules_mapping[provision_rule]['debit'] = '400008'
        rules_mapping[provision_rule]['credit'] = '202001'

        leave_provision_rule = self.env.ref('l10n_ae_hr_payroll.uae_annual_leave_provision_salary_rule')
        rules_mapping[leave_provision_rule]['debit'] = '400007'
        rules_mapping[leave_provision_rule]['credit'] = '201006'

        social_company_contribution_rule = self.env.ref('l10n_ae_hr_payroll.uae_social_insurance_company_contribution_salary_rule')
        rules_mapping[social_company_contribution_rule]['debit'] = '400073'
        rules_mapping[social_company_contribution_rule]['credit'] = '201021'

        social_employee_contribution_rule = self.env.ref('l10n_ae_hr_payroll.uae_social_insurance_employee_contribution_salary_rule')
        rules_mapping[social_employee_contribution_rule]['debit'] = '201021'

        dews_rule = self.env.ref('l10n_ae_hr_payroll.uae_dews_salary_rule')
        rules_mapping[dews_rule]['debit'] = '201022'

        annual_leaves_allowance_rule = self.env.ref('l10n_ae_hr_payroll.uae_annual_leaves_eos_allowance_salary_rule')
        rules_mapping[annual_leaves_allowance_rule]['debit'] = '201006'

        annual_leaves_deduction_rule = self.env.ref('l10n_ae_hr_payroll.uae_annual_leaves_eos_deduction_salary_rule')
        rules_mapping[annual_leaves_deduction_rule]['debit'] = '201006'

        reimbursement_rule = self.env.ref('l10n_ae_hr_payroll.l10n_ae_hr_payroll_uae_employee_payroll_structure_reimbursement_salary_rule')
        rules_mapping[reimbursement_rule]['debit'] = '201002'

        instant_pay_net_rule = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_net_salary')
        rules_mapping[instant_pay_net_rule]['credit'] = '201002'

        expenses_reimbursement_rule = self.env.ref('l10n_ae_hr_payroll.l10n_ae_hr_payroll_uae_employee_payroll_structure_expenses_reimbursement')
        rules_mapping[expenses_reimbursement_rule]['debit'] = '201002'

        net_rule = self.env['hr.salary.rule'].search([
            ('struct_id', '=', self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure').id),
            ('code', '=', 'NET')
        ], limit=1)
        rules_mapping[net_rule]['credit'] = '201002'

        self._configure_payroll_account(
            companies,
            "AE",
            account_codes=account_codes,
            rules_mapping=rules_mapping,
            default_account=default_account)
