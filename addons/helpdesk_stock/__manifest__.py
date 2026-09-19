# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Helpdesk Stock',
    'category': 'Services/Helpdesk',
    'summary': 'Project, Tasks, Stock',
    'depends': ['helpdesk_sale', 'stock'],
    'description': """
Manage Product returns from helpdesk tickets
    """,
    'data': [
        'wizard/stock_picking_return_views.xml',
        'views/stock_picking_views.xml',
        'views/helpdesk_ticket_views.xml',
        'data/mail_templates.xml',
    ],
    'demo': ['data/helpdesk_stock_demo.xml'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
