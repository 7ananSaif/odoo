# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Account Fiscal Report',
    'category': 'Accounting/Accounting',
    'summary': 'Account Fiscal Report',
    'description': 'Account Fiscal Report',
    'version': '1.0',
    'depends': ['account_reports'],
    'data': [
        'data/account_fiscal_report.xml',
        'security/ir.model.access.csv',
        'security/account_fiscal_categories_security.xml',
        'views/account_account_views.xml',
        'views/account_fiscal_category_views.xml',
        'views/account_fiscal_report_views.xml',
        'data/account_return_check_template.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'account_fiscal_categories/static/src/components/**/*',
        ],
    },
}
