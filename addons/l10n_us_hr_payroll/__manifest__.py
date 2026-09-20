# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'United States - Payroll',
    'countries': ['us'],
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr_payroll',
        'hr_work_entry_holidays',
        'hr_payroll_holidays',
        'base_address_extended',
        'l10n_us',  # for l10n_us_bank_account_type
    ],
    'auto_install': ['hr_payroll'],
    'version': '1.0',
    'description': """
United States Payroll Rules.
============================

    * Employee Details
    * Employee Contracts
    * Passport based Contract
    * Allowances/Deductions
    * Allow to configure Basic/Gross/Net Salary
    * Employee Payslip
    * Integrated with Leaves Management
    """,
    'data': [
        'data/res_country_data.xml',
        'data/res.city.csv',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_contract_type_data.xml',
        'views/hr_payroll_report.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_rule_parameters_data.xml',
        'data/res_partner_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/hr_salary_rule_data.xml',
        'views/report_payslip_templates.xml',
        'views/hr_contract_template_views.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_views.xml',
        'views/l10n_us_940_views.xml',
        'views/l10n_us_941_views.xml',
        'views/l10n_us_w2_views.xml',
        'views/l10n_us_worker_compensation_views.xml',
        'views/hr_leave_type_views.xml',
        'views/hr_views.xml',
        'data/menuitems.xml',
        'data/hr_payroll_dashboard_warning_data.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
    ],
    'demo': [
        'data/l10n_us_hr_payroll_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
