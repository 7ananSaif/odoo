# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Bangladesh - Accounting Reports',
    'version': '1.0.0',
    'description': """
Accounting reports for Bangladesh
============================================
- Corporate tax report
    """,
    'depends': [
        'account_reports',
        'l10n_bd',
    ],
    'data': [
        'data/account_return_data.xml',
        'data/corporate_tax_report.xml',
        'views/account_report_menu_view.xml',
        'views/res_config_settings_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
