{
    'name': 'ESG HR Fleet',
    'version': '1.0',
    'summary': "Measure fleet emissions based on your employees' commuting distance and vehicle data.",
    'depends': [
        'esg',
        'hr_fleet',
    ],
    'data': [
        'data/esg_hr_fleet_data.xml',
        'security/esg_hr_fleet_security.xml',
        'security/ir.model.access.csv',
        'report/esg_employee_commuting_report_views.xml',
        'views/esg_menus.xml',
        'views/res_config_settings_views.xml',
        'wizard/employee_commuting_emissions_wizard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'esg_hr_fleet/static/src/**/*',
            ('remove', 'esg_hr_fleet/static/src/views/esg_employee_commuting_report_pivot/**'),
        ],
        'web.assets_backend_lazy': [
            'esg_hr_fleet/static/src/views/esg_employee_commuting_report_pivot/**',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
