# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'United Arab Emirates - Accounting Reports',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
        Accounting reports:
        - Corporate Tax Report
    """,
    'depends': ['l10n_ae', 'account_reports', 'account_fiscal_categories'],
    'installable': True,
    'data': [
        'data/corporate_tax_report.xml',
        'data/account_return_data.xml',
        'data/actions.xml',
        'data/menuitems.xml',
        'data/account.account.tag.csv',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_ae_reports/static/src/*',
        ],
    },
    'post_init_hook': '_l10n_ae_reports_post_init',
    'auto_install': ['l10n_ae', 'account_reports', 'account_fiscal_categories'],
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
