# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Project Helpdesk',
    'version': '1.0',
    'category': 'Services',
    'summary': 'Project helpdesk',
    'description': 'Bridge created to convert tickets to tasks and tasks to tickets',
    'depends': ['project_enterprise', 'helpdesk'],
    'data': [
        'security/ir.model.access.csv',
        'views/helpdesk_ticket_views.xml',
        'views/project_task_views.xml',
        'wizard/helpdesk_ticket_convert_wizard_views.xml',
        'wizard/project_task_convert_wizard_views.xml',
    ],
    'demo': [
        'data/helpdesk_ticket_demo.xml',
        'data/helpdesk_ticket_convert_wizard_demo.xml',
        'data/project_task_demo.xml',
        'data/mail_message_demo.xml',
        'data/project_task_convert_wizard_demo.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
