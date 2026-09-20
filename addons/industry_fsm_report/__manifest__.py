# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Field Service Reports',
    'category': 'Services/Field Service',
    'summary': 'Create Reports for Field service technicians',
    'description': """
Create Reports for Field Service
================================

""",
    'depends': ['worksheet', 'industry_fsm', 'web_studio'],
    'data': [
        'security/industry_fsm_report_security.xml',
        'security/ir.model.access.csv',
        "views/project_project_views.xml",
        "views/project_portal_project_task_templates.xml",
        "views/project_task_views.xml",
        "views/worksheet_template_views.xml",
        "views/res_config_settings_views.xml",
        'report/project_task_burndown_chart_report_views.xml',
        'report/report_industry_fsm_worksheet_custom_templates.xml',
        'data/worksheet_template_data.xml',
        'wizard/worksheet_template_load_wizard_views.xml',
        "views/industry_fsm_report_menus.xml",
    ],
    'demo': [
        'data/worksheet_template_demo.xml',
        'data/project_task_demo.xml',
    ],
    'post_init_hook': 'post_init',
    'auto_install': ['industry_fsm', 'web_studio'],
    'assets': {
        'web.assets_backend': [
            'industry_fsm_report/static/src/js/tours/industry_fsm_report_tour.js',
        ],
        'web.assets_frontend': [
            'industry_fsm_report/static/src/js/tours/industry_fsm_report_tour.js',
        ],
        'web.assets_tests': [
            'industry_fsm_report/static/tests/tours/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
