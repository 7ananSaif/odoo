# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mobile',
    'category': 'Hidden',
    'summary': 'Odoo Mobile Core module',
    'version': '1.0',
    'description': """
This module provides the core of the Odoo Mobile App.
        """,
    'depends': [
        'web_enterprise',
    ],
    'data': [
        'views/views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'web_mobile/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            "web_mobile/static/tests/**/*.test.js",
        ],
    },
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
