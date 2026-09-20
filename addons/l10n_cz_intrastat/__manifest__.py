{
    'name': 'Czechian Intrastat Declaration',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Generates Intrastat XML report for declaration
Based on invoices.
Adds the possibility to specify the origin country of goods and the partner VAT in the Intrastat XML report.
    """,
    'depends': ['account_intrastat', 'l10n_cz_reports'],
    'data': [
        'data/account_return_data.xml',
        'security/ir.model.access.csv',
        'wizard/intrastat_goods_submission_wizard.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
