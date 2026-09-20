# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'ESG',
    'version': '1.0',
    'category': 'ESG',
    'summary': "Calculate and report your company's Environmental, Social, and Governance impact.",
    'depends': [
        'account_reports',
        'web_hierarchy',
    ],
    'data': [
        'security/esg_security.xml',
        'security/ir.model.access.csv',
        'data/esg_database_data.xml',
        'data/esg_emission_source_data.xml',
        'data/esg_gas_data.xml',
        'data/carbon_report.xml',
        'report/esg_carbon_emission_report_views.xml',
        'wizard/factors_auto_assignment_wizard_views.xml',
        'views/account_move_views.xml',
        'views/esg_emission_factor_views.xml',
        'views/esg_emission_source_views.xml',
        'views/esg_gas_views.xml',
        'views/esg_database_views.xml',
        'views/esg_other_emission_views.xml',
        'views/esg_menus.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'esg/static/src/**/*',
            ('remove', 'esg/static/src/views/esg_carbon_emission_graph/**'),
            ('remove', 'esg/static/src/views/esg_carbon_emission_pivot/**'),
            ('remove', 'esg/static/src/scss/*.dark.scss'),
        ],
        'web.assets_web_dark': [
            'esg/static/src/scss/*.dark.scss',
        ],
        'web.assets_backend_lazy': [
            'esg/static/src/views/esg_carbon_emission_graph/**',
            'esg/static/src/views/esg_carbon_emission_pivot/**',
        ],
        'web.assets_unit_tests': [
            'esg/static/tests/esg_models.js',
            'esg/static/tests/**/*.test.js',
        ],
    },
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
