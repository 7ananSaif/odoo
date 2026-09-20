# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Argentinean Accounting IVA Simple Export',
    'version': '1.0',
    'author': 'Odoo S.A.',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'IVA Simple Reporting for Argentinean Localization',
    'description': """
* Add export of IVA Simple Tax Report.
""",
    'depends': [
        'l10n_ar_reports',
    ],
    'data': [
        'data/account.account.tag.csv',
        'data/l10n_ar.arca.activity.csv',
        'views/l10n_ar_arca_activity_views.xml',
        'views/account_account_views.xml',
        'views/res_config_settings_view.xml',
        'security/ir.model.access.csv',
    ],
    'auto_install': True,
    'installable': True,
    'license': 'OEEL-1',
}
