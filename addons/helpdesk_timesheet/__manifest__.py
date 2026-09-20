# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Helpdesk Timesheet',
    'category': 'Services/Helpdesk',
    'summary': 'Project, Tasks, Timesheet',
    'depends': ['timesheet_grid', 'project_helpdesk'],
    'description': """
- Allow to set project for Helpdesk team
- Track timesheet for a task from a ticket
    """,
    'data': [
        'security/ir.model.access.csv',
        'security/helpdesk_timesheet_security.xml',
        'views/helpdesk_team_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/project_project_views.xml',
        'views/hr_timesheet_views.xml',
        'report/helpdesk_sla_report_analysis_views.xml',
        'report/helpdesk_ticket_report_analysis_views.xml',
        'report/report_timesheet_templates.xml',
        'report/timesheets_analysis_report_views.xml',
    ],
    'assets': {
        'web.assets_tests': [
            'helpdesk_timesheet/static/tests/tours/**',
        ],
        'web.assets_backend': [
            'helpdesk_timesheet/static/src/**/*',
            ('remove', 'helpdesk_timesheet/static/src/views/**'),
        ],
        'web.assets_backend_lazy': [
            'helpdesk_timesheet/static/src/views/**',
        ],
        'web.assets_unit_tests': [
            "helpdesk_timesheet/static/tests/*",
        ],
    },
    'demo': [
        'data/project_project_demo.xml',
        'data/helpdesk_team_demo.xml',
        'data/helpdesk_ticket_demo.xml',
        'data/account_analytic_line_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_helpdesk_timesheet_post_init',
    'uninstall_hook': '_helpdesk_timesheet_uninstall',
}
