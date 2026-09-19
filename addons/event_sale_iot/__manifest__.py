{
    'name': "IoT for Event/Sale",
    'summary': "Use IoT device integrations for events",
    'description': """
Bridge module for Event/Sale/IoT. Only used to prevent auto-printing if a registration is not yet sold.
""",
    'category': 'Marketing/Events',
    'version': '1.0',
    'depends': ['iot', 'event_sale'],
    'assets': {
        'web.assets_backend': [
            'event_sale_iot/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
