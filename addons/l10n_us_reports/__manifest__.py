# -*- coding: utf-8 -*-
{
    'name': 'US - Accounting Reports',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for US
    """,
    'website': 'https://www.odoo.com/app/accounting',
    'depends': [
        'l10n_us_account', 'account_reports'
    ],
    'data': [
        'data/account_return_data.xml',
        'data/tax_report.xml',
        'data/balance_sheet.xml',
        'data/profit_and_loss.xml',
    ],
    'installable': True,
    'post_init_hook': '_l10n_us_reports_post_init',
    'auto_install': ['l10n_us_account', 'account_reports'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
