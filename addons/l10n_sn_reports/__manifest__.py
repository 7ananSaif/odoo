{
    'name': 'Sénégal - Accounting Reports',
    'version': '1.0',
    'description': """
Accounting reports for Sénégal
============================================
- Corporate tax report
    """,
    'depends': [
        'account_reports',
        'l10n_sn',
    ],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
