# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Point of Sale Settle Due',
    'version': '1.0',
    'category': 'Point of Sale',
    'sequence': 6,
    'summary': "Settle partner's due in the POS UI.",
    'depends': ['point_of_sale', 'account_followup'],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'views/pos_order_views.xml',
        'views/account_move_views.xml',
        'data/pos_settle_due_data.xml',
    ],
    'assets': {
        'web.assets_unit_tests': [
            'pos_settle_due/static/tests/unit/**/*',
            ('remove', 'pos_settle_due/static/tests/unit/utils.js'),
        ],
        'point_of_sale._assets_pos': [
            'pos_settle_due/static/src/**/*',
        ],
        'web.assets_tests': [
            'pos_settle_due/static/tests/tours/**/*'
        ],
        'point_of_sale.assets_qunit_tests': [
            'pos_settle_due/static/tests/unit/**/*',
        ],
    }
}
