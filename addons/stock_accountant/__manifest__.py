# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Stock Accounting",
    'version': "1.0",
    'category': 'Supply Chain/Inventory',
    'summary': "Bridge between Stock and Accounting",
    'description': """
Filters the stock lines out of the reconciliation widget
    """,
    'depends': ['stock_account', 'account_accountant', 'account_reports'],
    'data': [
        'report/stock_valuation_report.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
