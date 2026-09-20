# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Switzerland - Swissdec Certified ELM 5.0 - Payroll',
    'icon': '/account/static/description/l10n.png',
    'countries': ['ch'],
    'category': 'Human Resources/Payroll',
    'depends': ['hr_payroll', 'hr_work_entry_holidays', 'hr_payroll_holidays', 'iap'],
    'auto_install': ['hr_payroll'],
    'version': '1.0',
    'description': """
Switzerland Payroll Rules.
==========================

    * Employee Details
    * Employee Contracts
    * Passport based Contract
    * Allowances/Deductions
    * Allow to configure Basic/Gross/Net Salary
    * Employee Payslip
    * Integrated with Leaves Management
    * Compute payslips according to ELM 5 standard
    """,
    'data': [
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/report_paperformat_data.xml',
        'data/hr_swiss_leave_types.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_rule_parameters_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_contract_type_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_template_views.xml',
        'views/l10n_ch_transmitter_mixin_views.xml',
        'views/res_config_settings_views.xml',
        'views/l10n_ch_location_unit_views.xml',
        'views/hr_contract_type_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/l10n_ch_individual_account_views.xml',
        'views/l10n_ch_monthly_summary_views.xml',
        'views/l10n_ch_social_insurance_views.xml',
        'views/l10n_ch_lpp_insurance_views.xml',
        'views/l10n_ch_accident_insurance_views.xml',
        'views/l10n_ch_additional_accident_insurance_views.xml',
        'views/l10n_ch_sickness_insurance_views.xml',
        'views/l10n_ch_compensation_fund_views.xml',
        'views/l10n_ch_employee_is_line.xml',
        'views/l10n_ch_hr_payroll_salary_certificate.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payslip_run_views.xml',
        'views/l10n_ch_absence_views.xml',
        'views/l10n_ch_avs_income_splits_views.xml',
        'views/l10n_ch_declaration_bvg_lpp_views.xml',
        'views/l10n_ch_declaration_ema_views.xml',
        'views/l10n_ch_declaration_salary_certificate_views.xml',
        'views/l10n_ch_declaration_source_tax_views.xml',
        'views/l10n_ch_declaration_statistics_views.xml',
        'views/l10n_ch_declaration_views.xml',
        'views/l10n_ch_declaration_yearly_retrospective_views.xml',
        'views/l10n_ch_hr_payroll_reports.xml',
        'views/hr_payroll_report.xml',
        'views/l10n_ch_hr_payroll_wage_types_views.xml',
        'views/l10n_ch_monthly_wage_types_view.xml',
        'views/l10n_ch_res_company_views.xml',
        'views/l10n_ch_salary_certificate_profile_views.xml',
        'views/l10n_ch_source_tax_institution.xml',
        'views/l10n_ch_swissdec_job_dialog_message.xml',
        'views/l10n_ch_swissdec_job_views.xml',
        'views/l10n_ch_yearly_values_views.xml',
        'views/l10n_ch_hr_payroll_interoperability_views.xml',
        'views/l10n_ch_occupation_views.xml',
        'wizard/l10n_ch_tax_rate_import_views.xml',
        'wizard/l10n_ch_hr_payroll_employee_lang_views.xml',
        'report/l10n_ch_monthly_summary_template.xml',
        'report/l10n_ch_individual_account_template.xml',
        'report/l10n_ch_master_data_report.xml',
        'report/l10n_ch_swiss_payslip_report.xml',
        'report/l10n_ch_wage_type_report.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/menuitems.xml',
    ],
    'demo': [
        'data/l10n_ch_hr_payroll_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_ch_hr_payroll/static/src/**/*',
        ],
        'web.report_assets_common': [
            'l10n_ch_hr_payroll/static/src/scss/*',
        ]
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
