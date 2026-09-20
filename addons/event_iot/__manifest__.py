{
    'name': "IoT for Events",
    'summary': "Use IoT device integrations for events",
    'description': """
Allows using a compatible printer to print Event badges upon checking in.
""",
    'category': 'Marketing/Events',
    'version': '1.0',
    'depends': ['iot', 'event'],
    'data': [
        'report/event_iot_templates.xml',
        'report/event_iot_reports.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'event_iot/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
