# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Oman - Accounting Reports',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'author': 'Odoo S.A.',
    'description': """
Oman - Accounting Reports
=================================================================
Oman accounting enterprise features.
Activates:
- Tax Return
""",
    'depends': [
        'l10n_om',
        'account_reports',
    ],
    'auto_install': True,
    'installable': True,
    'data': [
        'data/account_report_data.xml',
    ],
    'license': 'OEEL-1',
}
