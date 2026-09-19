# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Compare timesheets and forecast for your projects',
    'version': '1.0',
    'category': 'Services/Project',
    'description': """
Compare timesheets and forecast for your projects.
==================================================

In your project plan, you can compare your timesheets and your forecast to better schedule your resources.
    """,
    'website': 'https://www.odoo.com/app/project',
    'depends': ['project_timesheet_forecast', 'sale_timesheet', 'sale_project_forecast'],
    'data': [
        'views/planning_slot_views.xml',
        'views/project_project_views.xml',
        'report/planning_analysis_report_views.xml',
        'report/project_timesheet_forecast_report_analysis_views.xml',
    ],
    'demo': [
        'data/planning_role_demo.xml',
        'data/hr_employee_demo.xml',
        'data/product_product_demo.xml',
        'data/sale_order_line_demo.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
