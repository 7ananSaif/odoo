# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Account Batch Payment Reconciliation',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Allows using Reconciliation with the Batch Payment feature.',
    'depends': ['account_accountant', 'account_batch_payment'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'account_accountant_batch_payment/static/src/components/**/*',
        ],
    }
}
