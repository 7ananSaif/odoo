# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Helpdesk FSM - Sale',
    'description': """
Bridge between Helpdesk and Industry FSM Sale
    """,
    'summary': 'Project, Helpdesk, FSM, Timesheet and Sale Orders',
    'category': 'Services/Helpdesk',
    'depends': ['helpdesk_fsm', 'helpdesk_sale_timesheet', 'industry_fsm_sale'],
    'data': [
        'views/project_project_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
