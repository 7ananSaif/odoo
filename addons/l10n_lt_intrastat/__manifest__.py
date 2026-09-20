# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Lithuanian Intrastat Declaration',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
        Generates Intrastat XML report for declaration.
        Adds the possibility to specify the origin country of goods and the partner VAT in the Intrastat XML report.
    """,
    'depends': ['l10n_lt', 'account_intrastat'],
    'data': [
        'data/account_return_data.xml',
        'data/intrastat_export.xml',
        'data/code_region_data.xml',
        'security/ir.model.access.csv',
        'wizard/intrastat_goods_submission_wizard.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
