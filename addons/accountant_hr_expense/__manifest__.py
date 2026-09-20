# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Accounting - Expense',
    'category': 'Accounting/Accounting',
    'version': '1.0',
    'description': """
Accounting Expense Bridge
""",
    'website': 'https://www.odoo.com/app/accounting',
    'depends': ['accountant', 'hr_expense'],
    'data': [
        'views/account_return_check_template.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',

}
