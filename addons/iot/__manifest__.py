# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Internet of Things',
    'category': 'Administration/IoT',
    'sequence': 250,
    'summary': 'Basic models and helpers to support Internet of Things.',
    'description': """
This module provides management of your IoT Boxes inside Odoo.
""",
    'depends': ['mail', 'iot_base'],
    'data': [
        'wizard/add_iot_box_views.xml',
        'wizard/select_printers_views.xml',
        'security/iot_security.xml',
        'security/ir.model.access.csv',
        'views/iot_views.xml',
    ],
    'demo': [
        'demo/iot_demo.xml'
    ],
    'installable': True,
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'iot/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'iot/static/src/network_utils/iot_websocket.js',
            'iot/static/src/network_utils/iot_webrtc.js',
            'iot/static/tests/unit/**/*',
        ],
        'web.assets_tests': [
            ('include', 'iot.assets_tests'),
        ],
        'iot.assets_tests': [
            'iot/static/tests/tours/**/*',
        ],
    }
}
