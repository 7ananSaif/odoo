# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Sales Timesheet: Invoicing",

    'summary': "Configure timesheet invoicing",

    'description': """
When invoicing timesheets, allows invoicing either all timesheets
linked to an SO, or only the validated timesheets
    """,

    'category': 'Sales/Sales',
    'version': '0.1',

    'depends': ['sale_timesheet', 'timesheet_grid'],
    'data': [
        'data/hr_employee_tip_data.xml',
        'data/ir_exports_line_data.xml',
        'security/ir.model.access.csv',
        'security/sale_timesheet_enterprise_security.xml',
        'views/account_move_views.xml',
        'views/hr_timesheet_tip_views.xml',
        'views/hr_timesheet_views.xml',
        'views/hr_employee_views.xml',
        'views/project_task_views.xml',
        'views/project_sharing_project_task_views.xml',
        'views/res_config_settings_views.xml',
        'views/project_portal_project_task_template.xml',
        'wizard/sale_advance_payment_inv_views.xml',
        'wizard/edit_billable_time_target_views.xml',
        'report/timesheets_analysis_report_views.xml',
        'views/sale_timesheet_enterprise_menus.xml',
    ],
    'demo': [
        'data/account_analytic_line_demo.xml',
        'data/hr_employee_demo.xml',
        'data/project_task_demo.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'sale_timesheet_enterprise/static/src/**/*',
            ('remove', 'sale_timesheet_enterprise/static/src/views/timesheet_analysis_pivot/**'),
            ('remove', 'sale_timesheet_enterprise/static/src/views/timesheet_grid/**'),
            ('remove', 'sale_timesheet_enterprise/static/src/views/timesheet_leaderboard_timer_grid/**'),
        ],
        'web.assets_backend_lazy': [
            'sale_timesheet_enterprise/static/src/components/**',
            'sale_timesheet_enterprise/static/src/views/timesheet_analysis_pivot/**',
            'sale_timesheet_enterprise/static/src/views/timesheet_grid/**',
            'sale_timesheet_enterprise/static/src/views/timesheet_leaderboard_timer_grid/**',
        ],
        'web.assets_unit_tests': [
            'sale_timesheet_enterprise/static/tests/**/*',
        ],
    }
}
