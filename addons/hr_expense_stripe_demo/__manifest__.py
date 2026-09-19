# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Expense cards: Demo',
    'version': '1.0',
    'category': 'Human Resources/Expenses',
    'sequence': 75,
    'summary': 'Create and manage company expense cards via Stripe: Demo',
    'author': 'Odoo S.A.',
    'description': """Stripe Issuing integration for expenses: Demo module for testing and demonstration purposes""",
    'website': 'https://www.odoo.com/app/expenses',
    'depends': ['hr_expense_stripe'],
    'data': [
        'views/hr_expense_stripe_card_views.xml',

        'wizard/hr_expense_stripe_topup_wizard.xml',
        'wizard/hr_expense_stripe_test_purchase_wizard.xml',
        'wizard/hr_expense_stripe_test_shipping_wizard.xml',

        'security/ir.model.access.csv',
    ],
    'assets': {},
    'post_init_hook': '_post_init_hook_setup_issuing_demo',
    'installable': True,
    'license': 'LGPL-3',
}
