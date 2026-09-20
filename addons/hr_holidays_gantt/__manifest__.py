{
    'name': "Time off Gantt",
    'summary': """Gantt view for Time Off Dashboard""",
    'description': """
    Gantt view for Time Off Dashboard
    """,
    'category': 'Human Resources',
    'version': '1.0',
    'depends': ['hr_holidays', 'hr_gantt'],
    'auto_install': True,
    'data': [
        'views/hr_holidays_gantt_view.xml',
    ],
    'assets': {
        'web.assets_backend_lazy': [
            'hr_holidays_gantt/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
