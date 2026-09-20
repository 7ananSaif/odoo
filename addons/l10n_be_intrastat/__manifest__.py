# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Belgian Intrastat Declaration',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Generates Intrastat XML report for declaration
Based on invoices.
Adds the possibility to specify the origin country of goods and the partner VAT in the Intrastat XML report.
    """,
    'depends': ['account_intrastat', 'l10n_be_reports'],
    'data': [
        'data/account.intrastat.code.csv',
        'security/ir.model.access.csv',
        'data/code_region_data.xml',
        'data/intrastat_export.xml',
        'data/intrastat_report_services_f02cms.xml',
        'data/intrastat_report_services_f01dgs.xml',
        'data/account_return_data.xml',
        'wizard/intrastat_goods_submission_wizard.xml'
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
