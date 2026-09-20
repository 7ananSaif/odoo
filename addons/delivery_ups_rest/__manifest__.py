# -*- coding: utf-8 -*-
{
    'name': "UPS Shipping",
    'summary': "Send your shippings through UPS and track them online. This new version of the UPS connector is compatible"
               "with the newest version of the UPS REST APIs available at https://developer.ups.com/",
    'category': 'Shipping Connectors',
    'version': '0.1',
    'application': True,
    'depends': ['stock_delivery', 'mail'],
    'data': [
        'data/ups_package_data.xml',
        'views/delivery_ups.xml',
        'views/sale_order_views.xml',
        'views/res_partner.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
