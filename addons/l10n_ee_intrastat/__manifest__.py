{
    'name': 'Estonia Intrastat Declaration',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': "Generates Intrastat XML report for declaration.",
    'depends': ['l10n_ee_reports', 'account_intrastat'],
    'data': [
        'data/account_return_data.xml',
        'data/intrastat_export.xml',
        'security/ir.model.access.csv',
        'wizard/intrastat_goods_submission_wizard.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
