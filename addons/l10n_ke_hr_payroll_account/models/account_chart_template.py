# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_ke(self, companies):
        account_codes = [
            '2210',
            '2230',
            '2231',
            '2232',
            '2233',
            '2234',
            '2235',
            '5109',
            '510910',
            '510920',
            '510930',
        ]
        default_account = '5109'
        rules_mapping = defaultdict(dict)

        # ==================================== #
        #          Kenya: Regular Pay          #
        # ==================================== #

        gross = self.env['hr.salary.rule'].search([
            ('struct_id', '=', self.env.ref('l10n_ke_hr_payroll.hr_payroll_structure_ken_employee_salary').id),
            ('code', '=', 'GROSS')
        ])
        rules_mapping[gross]['debit'] = '5109'

        ahl_amount = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_salary_ahl_amount')
        rules_mapping[ahl_amount]['credit'] = '2210'

        paye = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_salary_paye')
        rules_mapping[paye]['credit'] = '2210'

        nssf_amount = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_nssf_amount')
        rules_mapping[nssf_amount]['credit'] = '2230'

        nhif_amount = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_salary_nhif_amount')
        rules_mapping[nhif_amount]['credit'] = '2231'

        shif_amount = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_salary_shif_amount')
        rules_mapping[shif_amount]['credit'] = '2231'

        helb = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_helb')
        rules_mapping[helb]['credit'] = '2232'

        voluntary_medical_insurance = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_volontary_medical_insurance')
        rules_mapping[voluntary_medical_insurance]['credit'] = '2233'

        life_insurance = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_life_insurance')
        rules_mapping[life_insurance]['credit'] = '2234'

        education = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_education')
        rules_mapping[education]['credit'] = '2235'

        pension_contribution = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_salary_pension_contribution')
        rules_mapping[pension_contribution]['credit'] = '2230'

        nita_employer_cost = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employer_nita')
        rules_mapping[nita_employer_cost]['debit'] = '510930'
        rules_mapping[nita_employer_cost]['credit'] = '2210'

        nssf_employer_cost = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employer_nssf_employer')
        rules_mapping[nssf_employer_cost]['debit'] = '510910'
        rules_mapping[nssf_employer_cost]['credit'] = '2230'

        ahl_amount_employer = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employer_salary_ahl_amount')
        rules_mapping[ahl_amount_employer]['debit'] = '510920'
        rules_mapping[ahl_amount_employer]['credit'] = '2210'

        net = self.env['hr.salary.rule'].search([
            ('struct_id', '=', self.env.ref('l10n_ke_hr_payroll.hr_payroll_structure_ken_employee_salary').id),
            ('code', '=', 'NET')
        ])
        rules_mapping[net]['credit'] = '2220'

        self._configure_payroll_account(
            companies,
            "KE",
            account_codes=account_codes,
            rules_mapping=rules_mapping,
            default_account=default_account)
