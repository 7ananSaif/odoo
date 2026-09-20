# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Belgium - Disallowed Expenses Fleet',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'description': """
Disallowed Expenses Fleet Data for Belgium
    """,
    'depends': [
        'account_fiscal_categories_fleet',
        'l10n_be_fiscal_categories',
        'l10n_be_hr_payroll_fleet',
    ],
    'data': [
        'data/account_fiscal_categories.xml',
        'views/fleet_vehicle_views.xml',
    ],
    'installable': True,
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
