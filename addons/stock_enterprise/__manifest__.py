# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Stock enterprise",
    'version': "1.0",
    'category': 'Supply Chain/Inventory',
    'summary': "Advanced features for Stock",
    'description': """
Contains the enterprise views for Stock management
    """,
    'depends': ['stock', 'web_cohort', 'web_map'],
    'data': [
        'security/ir.model.access.csv',
        'security/stock_enterprise_security.xml',
        'views/res_config_settings_views.xml',
        'views/stock_move_views.xml',
        'views/stock_picking_map_views.xml',
        'report/stock_report_views.xml',
    ],
    'assets': {
        'web.assets_backend_lazy': [
            'stock_enterprise/static/src/**/*'
        ]
    },
    'installable': True,
    'auto_install': ['stock'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
