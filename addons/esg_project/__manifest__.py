{
    'name': 'ESG Project',
    'version': '1.0',
    'summary': "Create and manage ESG initiatives to act on your impact.",
    'depends': [
        'esg',
        'project_enterprise',
    ],
    'data': [
        'data/project_data.xml',
        'views/project_project_views.xml',
        'views/esg_menus.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'esg_project/static/src/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
