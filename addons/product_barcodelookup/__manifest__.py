{
    'name': "Product Barcode Lookup",
    'description': "This module allows you to create products from barcode using Barcode Lookup API Key",
    'category': 'Sales/Sales',
    'version': '1.0',
    'depends': ['product'],
    'data': [
        'security/ir.model.access.csv',
        'security/product_security.xml',
        'data/ir_cron_data.xml',
        'data/product_data.xml',
        'views/product_product_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/product_fetch_image_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'product_barcodelookup/static/src/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
