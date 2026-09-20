{
    'name': "Romania - Intrastat Declaration",
    'category': 'Accounting/Localizations/Reporting',
    'version': '1.0',
    'description': """
        Romania - Intrastat Declaration
    """,
    'depends': ['account_intrastat', 'l10n_ro_reports'],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
