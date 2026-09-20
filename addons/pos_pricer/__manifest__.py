# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'PoS Pricer',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'Display and change your products information on electronic Pricer tags',
    'data': [
        'security/ir.model.access.csv',
        'views/pricer_tag_views.xml',
        'views/pricer_store_views.xml',
        'views/pos_pricer_configuration.xml',
        'views/product_views.xml',
        'data/pricer_ir_cron.xml',
        'data/pos_pricer_data.xml',
        'data/pos_config_data.xml',
    ],
    'demo': [
        'demo/pricelist_data.xml', 
    ],
    'depends': ['product', 'point_of_sale'],
    'installable': True,
    'assets': {
        'web.assets_backend': [
            'pos_pricer/static/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
