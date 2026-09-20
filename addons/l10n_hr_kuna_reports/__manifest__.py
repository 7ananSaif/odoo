{
    'name': 'Croatia (Kuna) - Accounting Reports',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Croatia (Kuna)
    """,
    'depends': [
        'l10n_hr_kuna', 'account_reports'
    ],
    'data': [
        'data/account_return_data.xml',
    ],
    'installable': True,
    'auto_install': ['l10n_hr_kuna', 'account_reports'],
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
