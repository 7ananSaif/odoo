{
    'name': 'POS UrbanPiper - India',
    'category': 'Sales/Point of Sale',
    'description': """
This module integrates with UrbanPiper to receive and manage orders from Swiggy and Zomato (Food delivery providers for India).
    """,
    'depends': ['l10n_in', 'pos_urban_piper'],
    'data': [
        'data/pos_delivery_provider_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
