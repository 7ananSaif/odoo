# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Portugal - Accounting Reports',
    'version': '1.0',
    'description': """
Accounting reports for Portugal
================================

    """,
    'category': 'Accounting/Localizations/Reporting',
    'depends': ['l10n_pt', 'account_reports'],
    'data': [
        'data/account_return_data.xml',
        'data/profit_loss.xml',
        'data/balance_sheet.xml',
        'data/account_report_ec_sales_list_report.xml',
    ],
    'auto_install': ['l10n_pt', 'account_reports'],
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
