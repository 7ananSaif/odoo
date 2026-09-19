# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'WhatsApp-Calendar',
    'version': '1.0',
    'summary': 'Send whatsapp messages as event reminders',
    'description': 'Send whatsapp messages as event reminders',
    'category': 'WhatsApp',
    'depends': ['calendar', 'whatsapp'],
    'data': [
        'views/calendar_alarm_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
