# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'POS Self-Order / Online Payment / Preparation Display',
    'summary': 'Link between self orders paid online and the preparation display',
    'category': 'Sales/Point of Sale',
    'version': '1.0',
    'depends': ['pos_online_payment_self_order', 'pos_enterprise'],
    'installable': True,
    'auto_install': True,
    'assets': {
        'pos_self_order.assets_tests': [
            'pos_online_payment_self_order_preparation_display/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
