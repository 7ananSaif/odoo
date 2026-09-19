# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Worksheet for Maintenance',
    'version': '1.0',
    'category': 'Supply Chain/Maintenance',
    'summary': 'Create custom worksheets for Maintenance',
    'description': """
Create customizable worksheet templates for Maintenance
=======================================================

""",
    'depends': ['maintenance', 'worksheet'],
    'data': [
        'security/maintenance_worksheet_security.xml',
        'security/ir.model.access.csv',
        'views/maintenance_views.xml',
        'views/maintenance_worksheet_views.xml',
        'report/maintenance_custom_report.xml',
        'report/maintenance_custom_report_templates.xml',
    ],
    "demo": [
        'data/maintenance_worksheet_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
