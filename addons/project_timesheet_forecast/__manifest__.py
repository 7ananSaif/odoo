# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Timesheet and Planning',
    'version': '1.0',
    'category': 'Services/Timesheets',
    'sequence': 50,
    'summary': 'Compare timesheets and plannings',
    'depends': ['timesheet_grid', 'project_forecast'],
    'description': """
Compare timesheets and plannings
================================

Better plan your future schedules by considering time effectively spent on old plannings

""",
    'data': [
        'report/planning_analysis_report_views.xml',
        'report/project_timesheet_forecast_report_analysis_views.xml',
        'security/ir.model.access.csv',
        'data/ir_filters_data.xml',
        'views/planning_slot_views.xml',
        'views/project_timesheet_forecast_menus.xml',
        ],
    'demo': [
        'data/planning_slot_demo.xml',
        'data/account_analytic_line_demo.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'uninstall_hook': '_uninstall_hook',
    'assets': {
        'web.assets_backend_lazy': [
            'project_timesheet_forecast/static/src/**/*',
        ],
    },
}
