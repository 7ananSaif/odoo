{
    'name': 'Burkina Faso - Accounting Reports',
    'version': '1.0',
    'description': """
Accounting reports for Burkina Faso
============================================
- Corporate tax report
    """,
    'depends': [
        'account_reports',
        'l10n_bf',
    ],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
