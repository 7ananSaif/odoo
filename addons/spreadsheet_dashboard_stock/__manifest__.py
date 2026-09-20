# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet dashboard for stock",
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet',
    'description': 'Spreadsheet',
    'depends': ['spreadsheet_dashboard', 'stock_enterprise'],
    'data': [
        "data/dashboards.xml",
    ],
    'installable': True,
    'auto_install': ['stock_enterprise'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
