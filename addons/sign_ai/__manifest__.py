# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Sign AI Integration",
    'version': '1.0',
    'category': 'Hidden',
    'summary': "Sign AI integration",
    'depends': ['sign', 'ai'],
    'data': [
        'wizard/sign_send_request_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
