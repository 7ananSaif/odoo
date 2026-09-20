{
    'name': 'Point of Sale - UrbanPiper',
    'category': 'Sales/Point of Sale',
    'description': """
This module integrates with UrbanPiper to receive and manage orders from various food delivery platforms.
    """,
    'depends': ['pos_enterprise', 'pos_discount'],
    'data': [
        'data/res_config_settings_data.xml',
        'data/pos_delivery_provider_data.xml',
        'data/product_product_data.xml',
        'data/pos_account_fiscal_position_data.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/pos_category_views.xml',
        'views/product_views.xml',
        'views/pos_payment_method_views.xml',
        'wizard/pos_urban_piper_test_order.xml',
    ],
    'post_init_hook': '_urban_piper_post_init',
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_urban_piper/static/src/point_of_sale_overrirde/**/*',
            'pos_urban_piper/static/src/utils.js',
        ],
        'pos_preparation_display.assets': [
            'pos_urban_piper/static/src/pos_preparation_display_override/**/*',
        ],
        'web.assets_tests': [
            'pos_urban_piper/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'pos_urban_piper/static/tests/unit/**/*'
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
