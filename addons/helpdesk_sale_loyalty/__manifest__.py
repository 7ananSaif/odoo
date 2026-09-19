# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Helpdesk Sale Loyalty',
    'category': 'Services/Helpdesk',
    'summary': 'Project, Tasks, Sale Loyalty',
    'depends': ['helpdesk_sale', 'sale_loyalty'],
    'description': """
Generate Coupons from Helpdesks tickets
    """,
    'data': [
        'security/ir.model.access.csv',
        'wizard/helpdesk_sale_coupon_generate_views.xml',
        'wizard/helpdesk_sale_giftcard_generate_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/loyalty_card_views.xml',
    ],
    'demo': [
        'data/helpdesk_sale_coupon_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
