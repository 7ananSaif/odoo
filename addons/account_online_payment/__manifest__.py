{
    'name': 'Account Online Payment',
    'summary': 'Initiate online payments',
    'description': 'This module allows customers to pay their invoices online using various payment methods.',
    'depends': ['account_online_synchronization', 'account_batch_payment', 'account_iso20022'],
    'data': [
        'data/actions.xml',
        'data/activation_mail_template.xml',
        'data/success_mail_template.xml',
        'views/account_batch_payment_views.xml',
        'views/account_online_link_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_online_payment/static/src/components/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
