# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Morocco - Payroll with Accounting',
    'category': 'Human Resources',
    'countries': ['ma'],
    'depends': ['l10n_ma_hr_payroll', 'hr_payroll_account', 'l10n_ma'],
    'description': """
Accounting Data for Moroccan Payroll Rules.
=================================================
    """,

    'auto_install': True,
    'data': [
        'data/hr_salary_rule_data.xml',
    ],
    'demo': [
        'data/l10n_ma_hr_payroll_account_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
