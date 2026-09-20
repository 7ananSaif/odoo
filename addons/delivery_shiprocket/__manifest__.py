# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Shiprocket Shipping",
    'description': "Send your parcels through shiprocket and track them online",
    'category': 'Shipping Connectors',
    'sequence': 317,
    'version': '1.0',
    'application': True,
    'depends': ['stock_delivery', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/res_config_settings_views.xml',
        'views/delivery_carrier_views.xml',
        'views/stock_picking.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
