# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Payroll',
    'version': '1.0',
    'category': 'Productivity/Documents',
    'summary': 'Store employee payslips in the Document app',
    'description': """
Employee payslips will be automatically integrated to the Document app.
""",
    'website': ' ',
    'depends': ['documents_hr', 'hr_payroll'],
    'data': [
        'data/documents_tag_data.xml',
        'data/mail_template_data.xml',
        'data/ir_action_server_data.xml',
        'views/res_config_settings_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payroll_employee_declaration_views.xml',
        'data/hr_payroll_dashboard_warning_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'documents_hr_payroll/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
