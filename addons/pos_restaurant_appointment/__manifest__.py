# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale Restaurant Appointment',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'This module lets you manage online reservations for restaurant tables',
    'website': 'https://www.odoo.com/app/appointments',
    'depends': ['pos_restaurant', 'pos_appointment'],
    'auto_install': True,
    'data': [
        'views/appointment_resource_views.xml',
        'views/pos_restaurant_views.xml',
        'views/calendar_event_views.xml',
    ],
    'demo': [
        'demo/pos_restaurant_appointment_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_pos_restaurant_appointment_after_init',
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_restaurant_appointment/static/src/**/*',
        ],
        'web.assets_backend': [
            'pos_restaurant_appointment/static/src/backend/json_field_resource/**/*',
        ],
        'web.assets_tests': [
            'pos_restaurant_appointment/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'pos_restaurant_appointment/static/tests/unit/**/*'
        ],
    }
}
