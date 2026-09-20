# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'United Arab Emirates - Payroll',
    'author': 'Odoo S.A.',
    'countries': ['ae'],
    'category': 'Human Resources/Payroll',
    'description': """
United Arab Emirates Payroll and End of Service rules.
=======================================================
- Basic salary calculations
- EOS calculations
- Annual leaves provisions and EOS provisions
- Social insurance rules for locals
- Overtime rule for the other inputs case
- Sick-leaves calculations
- DEWS calculations
- EOS calculations for free zones (DMCC)
- Out of contract calculations
- Calculation for unused leaves for EOS calculation
- Additional other input rules for (bonus, commissions, arrears, etc.)
- Master payroll export
- WPS
    """,
    'depends': ['hr_payroll', 'hr_work_entry_holidays'],
    'auto_install': ['hr_payroll'],
    'data': [
        'views/hr_payroll_report.xml',
        'views/report_payslip_templates.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/hr_salary_rule_regular_pay_data.xml',
        'data/hr_salary_rule_instant_pay_data.xml',
        'views/hr_contract_template_views.xml',
        'views/hr_employee_views.xml',
        'data/hr_rule_parameter_data.xml',
        'views/hr_leave_type_views.xml',
        'views/res_bank_views.xml',
        'views/res_config_settings_view.xml',
        'wizard/hr_payroll_payment_report_wizard.xml',
        'report/report_hr_employee_salary_certificate_template.xml',
        'report/report_hr_employee_salary_certificate.xml'
    ],
    'demo': [
        'data/l10n_ae_hr_payroll_demo.xml'
    ],
    'license': 'OEEL-1',
}
