# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'PoS Preparation Display Restaurant',
    'version': '1.0.0',
    'category': 'Sales/Point of Sale',
    'sequence': 7,
    'summary': 'Display Orders for Preparation stage.',
    'depends': ['pos_restaurant', 'pos_enterprise'],
    'data': [
        'views/preparation_display_view.xml',
    ],
    'installable': True,
    'auto_install': True,
    'assets': {
        'pos_preparation_display.assets': [
            'pos_restaurant_preparation_display/static/src/app/**/*',
        ],
        'point_of_sale._assets_pos': [
            'pos_restaurant_preparation_display/static/src/override/**/*.js',
        ],
        'web.assets_tests': [
            'pos_restaurant_preparation_display/static/tests/tours/point_of_sale/**/*',
        ],
        'pos_preparation_display.assets_tour_tests': [
            'pos_restaurant_preparation_display/static/tests/tours/preparation_display/**/*',
        ],
    },
    'post_init_hook': '_pos_restaurant_preparation_display_post_init',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
