# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Sales Timesheet: Time Off",

    'summary': "Exclude the timeoff timesheet entries from the rank calculation in the Timesheets Leaderboard.",

    'description': """
        This bridge module is auto-installed when the modules sale_timesheet_enterprise and project_timesheet_holidays are installed.
    """,

    'category': 'Sales/Sales',
    'version': '0.1',

    'depends': ['sale_timesheet_enterprise', 'project_timesheet_holidays'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
