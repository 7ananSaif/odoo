{
    'name': "IoT for PoS/Event",
    'summary': "Use IoT device integrations for events",
    'description': """
Bridge module for PoS/Event/IoT. Used to print with IoT upon selling an event ticket.
""",
    'category': 'Marketing/Events',
    'version': '1.0',
    'depends': ['iot', 'pos_event'],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_event_iot/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
