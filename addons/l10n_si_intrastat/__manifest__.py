{
    'name': "Slovenian Intrastat Declaration",
    'category': 'Accounting/Localizations/Reporting',
    'description': """
        Slovenia - Intrastat report
    """,
    'depends': ['account_intrastat', 'l10n_si_reports'],
    'data': [
        'data/account_return_data.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
