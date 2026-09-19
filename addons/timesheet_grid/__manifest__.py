# Part of Odoo. See LICENSE file for full copyright and licensing details.
# YTI FIXME: This module should be named timesheet_enterprise
{
    'name': "Timesheets",
    'summary': "Track employee time on tasks",
    'description': """
* Timesheet submission and validation
* Activate grid view for timesheets
    """,
    'version': '1.0',
    'depends': ['project_enterprise', 'web_grid', 'hr_timesheet', 'timer', 'hr_org_chart'],
    'category': 'Services/Timesheets',
    'sequence': 65,
    'data': [
        'data/ir_cron_data.xml',
        'data/ir_config_parameter_data.xml',
        'data/mail_template_data.xml',
        'data/web_tour_data.xml',
        'security/timesheet_security.xml',
        'security/ir.model.access.csv',
        'views/account_analytic_line_views.xml',
        'views/project_task_views.xml',
        'views/hr_employee.xml',
        'views/timesheet_grid_menus.xml',
        'views/project_views.xml',
        'views/res_config_settings_views.xml',
        "report/timesheets_analysis_report_views.xml",
        'wizard/hr_timesheet_merge_wizard_views.xml',
        'wizard/hr_timesheet_stop_timer_confirmation_wizard_views.xml',
    ],
    'demo': [
        'data/account_analytic_line_demo.xml',
    ],
    'website': ' https://www.odoo.com/app/timesheet',
    'auto_install': ['web_grid', 'hr_timesheet'],
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'assets': {
        'web.assets_backend': [
            'timesheet_grid/static/src/**',

            ('remove', 'timesheet_grid/static/src/views/timer_timesheet_grid/**'),
            ('remove', 'timesheet_grid/static/src/views/timesheet_grid/**'),
            ('remove', 'timesheet_grid/static/src/views/timesheet_to_validate_grid/**'),
            ('remove', 'timesheet_grid/static/src/services/timesheet_grid_uom_service.js'),
            ('remove', 'timesheet_grid/static/src/components/timesheet_grid_many2one/**'),
            ('remove', 'timesheet_grid/static/src/components/timesheet_many2one_avatar_employee_grid_row/**'),
            ('remove', 'timesheet_grid/static/src/components/grid_timesheet_uom/**'),
            ('remove', 'timesheet_grid/static/src/js/views/timesheet_pivot/**'),
        ],
        'web.assets_backend_lazy': [
            'timesheet_grid/static/src/views/timer_timesheet_grid/**',
            'timesheet_grid/static/src/views/timesheet_grid/**',
            'timesheet_grid/static/src/views/timesheet_to_validate_grid/**',
            'timesheet_grid/static/src/services/timesheet_grid_uom_service.js',
            'timesheet_grid/static/src/components/timesheet_grid_many2one/**',
            'timesheet_grid/static/src/components/timesheet_many2one_avatar_employee_grid_row/**',
            'timesheet_grid/static/src/components/grid_timesheet_uom/**',
            'timesheet_grid/static/src/js/views/timesheet_pivot/**',
        ],
        'web.assets_tests': [
            'timesheet_grid/static/tests/tours/**',
        ],
        'web.assets_unit_tests': [
            "timesheet_grid/static/tests/**/*.test.js",
            "timesheet_grid/static/tests/hr_timesheet_models.js",
            "timesheet_grid/static/tests/timesheet_grid_timer_helpers.js",
        ],
    }
}
