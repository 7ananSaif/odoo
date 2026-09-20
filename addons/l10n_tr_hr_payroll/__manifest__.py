# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Türkiye - Payroll',
    'countries': ['tr'],
    'category': 'Human Resources/Payroll',
    'description': """
Türkiye Payroll and Tax Rules
=============================
- Social Security Premium/Insurance calculations for employment and unemployment
- Income tax calculations
- Stamp tax deductions
    """,
    'depends': ['hr_payroll'],
    'auto_install': ['hr_payroll'],
    'data': [
        'data/hr_rule_parameter_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/hr_salary_rule_data.xml',
        'views/hr_employee_views.xml',
        'report/report_hr_employee_employment_certificate.xml',
        'report/report_hr_employee_employment_certificate_template.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'demo':[
        'data/l10n_tr_hr_payroll_demo.xml'
    ]
}
