# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Belgium - Payroll with Accounting',
    'category': 'Human Resources',
    'countries': ['be'],
    'depends': ['l10n_be_hr_payroll', 'hr_payroll_account', 'l10n_be'],
    'description': """
Accounting Data for Belgian Payroll Rules.
==========================================
    """,

    'auto_install': True,
    'data':[
        'data/l10n_be_hr_payroll_account_data.xml',
        'data/hr_salary_rule_data.xml',
        'views/res_config_settings_views.xml',
        'views/l10n_be_274_XX_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
