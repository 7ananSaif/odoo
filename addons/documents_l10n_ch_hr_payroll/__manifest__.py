# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Swiss Payroll',
    'icon': '/account/static/description/l10n.png',
    'version': '1.0',
    'countries': ['ch'],
    'category': 'Human Resources/Payroll',
    'summary': 'Store individual accounts in Documents application',
    'description': """
Employees' individual account forms are automatically integrated to the Document app.
""",
    'website': ' ',
    'depends': ['documents_hr_payroll', 'l10n_ch_hr_payroll'],
    'data': [
        'views/l10n_ch_individual_account_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
