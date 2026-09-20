# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Whatsapp-Payment',
    'category': 'WhatsApp',
    'description': """This module Integrates Payment with WhatsApp""",
    'depends': ['payment', 'whatsapp'],
    'data': [
        'data/whatsapp_template_data.xml',
        'wizard/payment_link_wizard.xml'
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True
}
