# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Croatia - Accounting Reports',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Croatia
    """,
    'depends': [
        'l10n_hr', 'account_reports'
    ],
    'data': [
        'data/account_return_data.xml',
        'data/balance_sheet.xml',
        'data/profit_loss.xml',
        'security/ir.model.access.csv',
        'views/account_report_ec_sales_list_report.xml',
        'wizard/ec_sales_list_submission_wizard.xml',
    ],
    'installable': True,
    'auto_install': ['l10n_hr', 'account_reports'],
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
