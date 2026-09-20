{
    'name': "Rental",

    'summary': "Manage rental contracts, deliveries and returns",

    'description': """
Specify rentals of products (products, quotations, invoices, ...)
Manage status of products, rentals, delays
Manage user and manager notifications
    """,

    'website': "https://www.odoo.com/app/rental",

    'category': 'Sales/Sales',
    'sequence': 160,
    'version': '1.0',

    'depends': ['sale', 'web_gantt'],

    'data': [
        'security/ir.model.access.csv',
        'security/ir_rules.xml',

        'data/rental_data.xml',
        'data/rental_tour.xml',

        'views/product_pricelist_views.xml',
        'views/product_pricing_views.xml',
        'views/product_product_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_line_views.xml',
        'views/sale_temporal_recurrence_views.xml',
        'views/res_config_settings_views.xml',

        'report/rental_order_report_templates.xml',
        'report/rental_report_views.xml',

        'wizard/rental_processing_views.xml',

        'views/sale_renting_menus.xml',
    ],
    'demo': [
        'data/rental_demo.xml',
    ],
    'application': True,
    'pre_init_hook': '_pre_init_rental',
    'assets': {
        'web.assets_backend': [
            'sale_renting/static/src/js/**/*',
        ],
        'web.assets_backend_lazy': [
            'sale_renting/static/src/views/schedule_gantt/**',
        ],
        'web.assets_tests': [
            'sale_renting/static/tests/tours/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
