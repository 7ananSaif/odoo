# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Denmark - Accounting Reports',
    'version': '1.0',
    'author': 'Odoo House ApS',
    'website': 'https://odoohouse.dk',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Denmark
=================================
    """,
    'depends': [
        'l10n_dk',
        'account_reports',
        'account_saft',
        'documents_account',
    ],
    'data': [
        'data/balance_sheet.xml',
        'data/profit_loss.xml',
        'data/account_report_ec_sales_list_report.xml',
        'data/account_return_data.xml',
        'data/saft_report.xml',
        'data/documents_file_data.xml',
        'views/account_journal_dashboard.xml',
        'security/ir.model.access.csv',
        'wizard/ec_sales_list_submission_wizard.xml',
        'data/tax_report.xml',
        'views/template_rsu.xml',
        'wizard/tax_report_wizard.xml',
    ],
    'auto_install': [
        'l10n_dk',
        'account_reports',
    ],
    'license': 'OEEL-1',
}
