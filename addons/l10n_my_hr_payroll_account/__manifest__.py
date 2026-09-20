# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Malaysia - Payroll with Accounting',
    'version': '1.0',
    'countries': ['my'],
    'category': 'Human Resources',
    'description': """
Accounting Data for Malaysian Payroll Rules
===========================================
    """,
    'depends': ['hr_payroll_account', 'l10n_my', 'l10n_my_hr_payroll'],
    'data': [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    'demo': [
        'data/l10n_my_hr_payroll_account_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
