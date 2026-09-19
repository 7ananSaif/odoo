{
    'name': 'New Zealand - Accounting Reports',
    'version': '1.0',
    'description': """
Accounting reports for New Zealand
============================================
- Corporate tax report
    """,
    'depends': [
        'account_reports',
        'l10n_nz',
    ],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
