# -*- coding: utf-8 -*-

{
    'name': "Belgium - Payroll - Export to SD Worx",
    'countries': ['be'],
    'summary': "Export Work Entries to SD Worx",
    'description': "Export Work Entries to SD Worx",
    'category': "Human Resources",
    'version': '1.0',
    'depends': ['l10n_be_hr_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_payroll_dashboard_warning_data.xml',
        'data/hr_work_entry_type_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_work_entry_type_views.xml',
        'views/res_config_settings_views.xml',
        'views/hr_payroll_export_sdworx_views.xml',
    ],
    'demo': [
        'data/l10n_be_hr_payroll_sdworx_demo.xml',
        'data/hr_work_entry_type_data.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
