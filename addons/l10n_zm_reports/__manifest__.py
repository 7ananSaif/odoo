# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Zambia - Accounting Reports',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Zambia
================================
    - Financial Reports (Balance Sheet & Profit and Loss & Tax Report)
    """,
    'depends': [
        'l10n_zm_account',
        'account_reports'
    ],
    'data': [
        'data/account_return_data.xml',
        'data/profit_loss.xml',
        'data/balance_sheet.xml',
    ],
    'auto_install': True,
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
