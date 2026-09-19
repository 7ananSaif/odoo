{
    'name': "Spain - Intrastat Declaration",
    'category': 'Accounting/Localizations/Reporting',
    'description': """
        Spain - Intrastat Report
    """,
    'depends': [
        'account_intrastat',
        'l10n_es_reports'
    ],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
