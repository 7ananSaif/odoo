{
    'name': 'ESG HR',
    'version': '1.0',
    'summary': "Use your employee data to measure important ESG metrics (e.g. employee commuting, sex parity).",
    'depends': [
        'esg',
        'hr',
    ],
    'data': [
        'security/esg_hr_security.xml',
        'security/ir.model.access.csv',
        'report/esg_employee_report_views.xml',
        'views/esg_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'esg_hr/static/src/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
