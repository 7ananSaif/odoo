# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet dashboard for payroll",
    'version': '1.0',
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet',
    'description': 'Spreadsheet',
    'depends': ['spreadsheet_dashboard', 'hr_payroll'],
    'data': [
        "data/dashboards.xml",
    ],
    'installable': True,
    'auto_install': ['hr_payroll'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
