# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'UPS: Bill My Account',
    'category': 'Shipping Connectors',
    'summary': 'Bill to your UPS account number',
    'description': """
This module allows ecommerce users to enter their UPS account number and delivery fees will be charged on that account number.
    """,
    'depends': ['delivery_ups', 'website_sale'],
    'data': [
        'views/delivery_ups_templates.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_frontend': [
            'website_sale_ups/static/src/**/*',
        ],
    }
}
