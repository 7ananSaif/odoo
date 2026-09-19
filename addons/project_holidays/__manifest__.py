# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Project Time Off",
    'version': '1.0',
    'category': 'Services/Project',
    'summary': "Project and task integration with holidays",
    'description': """
Project and task integration with holidays
    """,
    'depends': ['project_enterprise', 'hr_holidays_gantt'],
    'data': [
        'views/project_task_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
