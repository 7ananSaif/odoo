# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Fiscal Categories on Fleets',
    'category': 'Accounting/Accounting',
    'summary': 'Manage fiscal categories with fleets',
    'version': '1.0',
    'depends': ['account_accountant_fleet', 'account_fiscal_categories'],
    'data': [
        'security/ir.model.access.csv',
        'data/account_fiscal_report.xml',
        'views/account_fiscal_category_views.xml',
        'views/fleet_vehicle_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_fiscal_categories_fleet/static/src/components/**/*',
        ],
    },
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
