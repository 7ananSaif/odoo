# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'IoT for PoS',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'Use IoT Devices in the PoS',
    'description': """
Allows to use in the Point of Sale the devices that are connected to an IoT Box.
Supported devices include payment terminals, receipt printers, scales and customer displays.
""",
    'depends': ['point_of_sale', 'iot'],
    'installable': True,
    'auto_install': True,
    'uninstall_hook': 'uninstall_hook',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'views/iot_views.xml',
        'views/pos_config_views.xml',
        'views/pos_printer_views.xml',
        'views/res_config_setting_views.xml',
        'wizard/auto_config_views.xml',
        'security/ir.model.access.csv',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'iot_base/static/src/network_utils/*',
            'iot_base/static/src/device_controller.js',
            'iot/static/src/overrides/network_utils/*',
            'iot/static/src/network_utils/*',
            'iot/static/src/iot_report_action.js',
            'iot/static/src/select_printer_wizard.js',
            'iot/static/src/client_action/delete_local_storage.js',
            'pos_iot/static/src/**/*',
            ('remove', 'pos_iot/static/src/backend/**/*'),
        ],
        'web.assets_tests': [
            'pos_iot/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'pos_iot/static/tests/unit/**/*'
        ],
        'web.assets_backend': [
            'pos_iot/static/src/backend/**/*',
        ],
    }
}
