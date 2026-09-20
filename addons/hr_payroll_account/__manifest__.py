# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Payroll Accounting',
    'category': 'Human Resources/Payroll',
    'description': """
Generic Payroll system Integrated with Accounting.
==================================================

    * Expense Encoding
    * Payment Encoding
    * Company Contribution Management
    """,
    'depends': ['hr_payroll', 'accountant', 'base_iban'],
    'data': [
        'data/hr_salary_rule_data.xml',
        'views/hr_payslip_run_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_template_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/res_partner_bank_views.xml',
    ],
    'demo': [
        'data/hr_payroll_account_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_payroll_account/static/src/**/*',
        ],
        'web.assets_tests': [
            'hr_payroll_account/static/tests/tours/**/*'
        ],
    },
    'pre_init_hook': '_salaries_account_journal_pre_init',
    'auto_install':  ['hr_payroll', 'accountant'],
    'post_init_hook': '_hr_payroll_account_post_init',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
