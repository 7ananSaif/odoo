# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Denmark - Intrastat',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Intrastat for Denmark
=====================
    """,
    'depends': [
        'l10n_dk_reports',
        'account_intrastat',
    ],
    'data': [
        'data/account_return_data.xml',
        'security/ir.model.access.csv',
        'wizard/intrastat_goods_submission_wizard.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
