# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'PoS Order Tracking Customer Display',
    'version': '1.0.0',
    'category': 'Sales/Point of Sale',
    'sequence': 7,
    'summary': 'Display customer\'s order status',
    'depends': ['pos_enterprise', 'pos_self_order'],
    'installable': True,
    'auto_install': True,
    'data': [
        'views/index.xml',
        'views/preparation_display_view.xml',
    ],
    'assets': {
        'pos_order_tracking_display.assets': [
            ("include", "point_of_sale.base_app"),
            'point_of_sale/static/src/utils.js',
            "point_of_sale/static/src/app/components/odoo_logo/*",
            'pos_order_tracking_display/static/src/**/*',
            'pos_enterprise/static/src/app/utils/utils.js'
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
