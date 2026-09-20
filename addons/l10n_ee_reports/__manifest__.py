# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Estonia - Accounting Reports',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting Reports for Estonia
    """,
    'author': 'Odoo SA',
    'depends': [
        'l10n_ee',
        'account_reports',
    ],
    'data': [
        'views/report_export_templates.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'data/balance_sheet.xml',
        'data/profit_and_loss.xml',
        'data/ic_supply_report.xml',
        'data/tax_report.xml',
        'data/kmd_inf/kmd_inf_report_part_a.xml',
        'data/kmd_inf/kmd_inf_report_part_b.xml',
        'data/kmd_inf/kmd_inf_report.xml',
        'data/account_return_data.xml',
        'security/ir.model.access.csv',
        'wizard/ec_sales_list_submission_wizard.xml',
        'wizard/kmd_inf_return_wizard.xml',
        'wizard/tax_return_type_wizard.xml',
    ],
    'installable': True,
    'auto_install': [
        'l10n_ee',
        'account_reports',
    ],
    'website': 'https://www.odoo.com/app/accounting',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'l10n_ee_reports/static/src/components/**/*',
        ],
    },
}
