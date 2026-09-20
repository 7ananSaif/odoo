# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Barcode for Batch Transfer',
    'version': '1.0',
    'category': 'Supply Chain/Inventory',
    'summary': "Add the support of batch transfers into the barcode view",
    'depends': ['stock_barcode', 'stock_picking_batch'],
    'data': [
        'views/stock_barcode_picking.xml',
        'views/stock_barcode_picking_batch.xml',
        'views/stock_move_line_views.xml',
        'views/stock_package_type_views.xml',
        'wizard/stock_barcode_cancel_operation.xml',
        'data/data.xml',
    ],
    'demo': [
        'data/stock_barcode_picking_batch_demo.xml',
    ],
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            'stock_barcode_picking_batch/static/src/**/*',
        ],
        'web.assets_tests': [
            'stock_barcode_picking_batch/static/tests/tours/**/*.js',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
