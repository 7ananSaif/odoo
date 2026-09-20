{
    'name': 'Taiwan - Accounting Reports',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Taiwan
================================
    """,
    'depends': [
        'l10n_tw',
        'account_reports'
    ],
    'data': [
        'data/profit_and_loss.xml',
        'data/balance_sheet.xml',
        'data/profit_and_loss_legacy.xml',
        'data/balance_sheet_legacy.xml',
    ],
    'auto_install': True,
    'installable': True,
    "icon": "/base/static/img/country_flags/tw.png",
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
