# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Sale Management for Rental",
    'version': '1.0',
    'category': 'Sales/Sales',
    'description': "This module adds management features to the sale renting app.",
    'depends': ['sale_renting', 'sale_management'],
    'data': [
        'views/sale_order_template_views.xml',
        'views/sale_renting_menus.xml',
    ],
    'demo': [
        'data/rental_management_demo.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
