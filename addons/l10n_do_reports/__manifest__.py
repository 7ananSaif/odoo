## -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Dominican Republic - Accounting Reports',
    'version': '1.0',
    'description': """
Accounting reports for Dominican Republic
    """,
    'category': 'Accounting/Localizations/Reporting',
    'depends': [
        'l10n_do',
        'account_reports',
    ],
    'data': [
        'data/account_return_data.xml',
        'data/profit_and_loss.xml',
        'data/balance_sheet.xml',
    ],
    'auto_install': True,
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
