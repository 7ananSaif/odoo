{
    'name': 'eCommerce Rental',
    'category': 'Website/Website',
    'summary': 'Sell rental products on your eCommerce',
    'version': '1.0',
    'description': """
This module allows you to sell rental products in your eCommerce with
appropriate views and selling choices.
    """,
    'depends': ['website_sale', 'sale_renting'],
    'data': [
        'security/ir.model.access.csv',
        'security/website_sale.xml',
        'data/product_snippet_template_data.xml',
        'views/product_views.xml',
        'views/res_config_settings_views.xml',
        'views/templates.xml',
        'views/snippets/snippets.xml',
        'views/snippets/s_rental_search.xml',
    ],
    'demo': [
        'data/demo.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'sale_renting/static/src/js/combo_configurator_dialog/*',
            'sale_renting/static/src/js/product_configurator_dialog/*',
            'website_sale_renting/static/src/interactions/**/*',
            'website_sale_renting/static/src/snippets/**/*.js',
            'website_sale_renting/static/src/scss/*.scss',
            ('before', 'website_sale/static/src/interactions/website_sale.js', 'website_sale_renting/static/src/js/*.js'),
        ],
        'web.assets_tests': [
            'website_sale_renting/static/tests/tours/**/*',
        ],
        'website.website_builder_assets': [
            'website_sale_renting/static/src/plugins/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
