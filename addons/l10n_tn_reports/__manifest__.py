# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Tunisia - Accounting Reports',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Tunisia
================================

     """,
    'depends': [
        'l10n_tn',
        'account_reports',
    ],
    'data': [
        'data/account_return_data.xml',
        'data/balance_sheet.xml',
        'data/profit_loss.xml',
    ],
    'auto_install': ['l10n_tn', 'account_reports'],
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
