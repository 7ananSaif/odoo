# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'POS Self Order IoT',
    'version': '1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'IoT in PoS Kiosk',
    'depends': ['pos_iot', 'pos_self_order'],
    'auto_install': True,
    "data": [
        "views/iot_views.xml",
        "views/res_config_settings.xml",
    ],
    "demo": [
        "demo/iot_demo.xml",
    ],
    'assets': {
        'pos_self_order.assets': [
            'web/static/lib/jquery/jquery.js',
            'iot_base/static/src/network_utils/*',
            'iot_base/static/src/device_controller.js',
            'iot/static/src/overrides/network_utils/*',
            'iot/static/src/network_utils/*',
            'pos_iot/static/src/app/utils/printer/iot_printer.js',
            'pos_iot/static/src/overrides/network_utils/iot_http_service.js',
            'point_of_sale/static/src/app/services/hardware_proxy_service.js',
            'pos_self_order_iot/static/src/overrides/models/*',
            'pos_self_order_iot/static/src/overrides/network_utils/*',
            'pos_self_order_iot/static/src/pages/**/*',
        ],
        'web.assets_backend': [
            'pos_self_order_iot/static/src/views/*',
        ],
        'pos_self_order.assets_tests': [
            ('include', 'iot.assets_tests'),
            "pos_self_order_iot/static/tests/tours/**/*",
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
