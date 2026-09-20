# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Lithuania - Payroll with Accounting',
    'author': 'Odoo',
    'version': '1.0',
    'countries': ['lt'],
    'category': 'Human Resources',
    'description': """
Accounting Data for Lithuania Payroll Rules
============================================
    """,
    'depends': ['hr_payroll_account', 'l10n_lt', 'l10n_lt_hr_payroll'],
    'data': [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    'demo': [
        'data/l10n_lt_hr_payroll_account_demo.xml',
    ],
    'license': 'OEEL-1',
    'auto_install': True,
}
