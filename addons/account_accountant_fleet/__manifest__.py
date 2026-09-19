# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Accounting/Fleet bridge',
    'category': 'Accounting/Accounting',
    'summary': 'Manage accounting with fleet features',
    'version': '1.0',
    'depends': ['account_fleet', 'account_accountant'],
    'author': 'Odoo S.A.',
    'data': [
         'views/account_move_views.xml',
     ],
    'license': 'OEEL-1',
    'auto_install': True,
}
