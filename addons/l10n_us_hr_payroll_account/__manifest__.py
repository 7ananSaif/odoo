# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'United States - Payroll with Accounting',
    'author': 'Odoo',
    'version': '1.0',
    'countries': ['us'],
    'category': 'Human Resources',
    'description': """
Accounting Data for United States Payroll Rules
===============================================
    """,
    'depends': ['hr_payroll_account', 'l10n_us_hr_payroll', 'l10n_us_payment_nacha'],
    'data': [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
        'views/hr_payslip_run_views.xml',
        'views/hr_payslip_views.xml',
        'wizard/hr_payroll_payment_report_wizard.xml',
    ],
    'demo': [
        'data/l10n_us_hr_payroll_account_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_us_hr_payroll_account/static/src/**/*',
        ],
    },
    'license': 'OEEL-1',
    'auto_install': True,
}
