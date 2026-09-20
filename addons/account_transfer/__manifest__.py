{
    'name': 'Account Transfers',
    'depends': ['account_accountant'],
    'description': """
Account Transfers
===========================
A helper model for managing transfers between accounts.
    """,
    'category': 'Accounting/Accounting',
    'data': [
        'data/cron.xml',
        'security/account_transfer_security.xml',
        'security/ir.model.access.csv',
        'views/transfer_model_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
