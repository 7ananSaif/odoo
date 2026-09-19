# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mexico - Payroll CFDI',
    'countries': ['mx'],
    'category': 'Human Resources/Payroll',
    'depends': ['l10n_mx_hr_payroll_account', 'l10n_mx_edi'],
    'auto_install': ['l10n_mx_hr_payroll_account'],
    'version': '1.0',
    'description': 'Adds CFDI to the payroll flow',
    'data': [
        'security/ir.model.access.csv',
        'data/report_paperformat_data.xml',
        'views/hr_payroll_report.xml',
        'data/4.0/cfdi.xml',
        'data/hr.contract.type.csv',
        'data/hr_payroll_structure_data.xml',
        'data/hr_work_entry_type_data.xml',
        'data/l10n.mx.concept.csv',
        'data/hr_salary_rule_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payslip_run_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/hr_work_entry_type_views.xml',
        'views/l10n_mx_concept_views.xml',
        'views/report_payslip_templates.xml',
        'views/res_config_settings_views.xml'
    ],
    'demo': [
        'data/l10n_mx_hr_payroll_account_edi_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_mx_hr_payroll_account_edi/static/src/**/*',
            ('remove', 'l10n_mx_hr_payroll_account_edi/static/src/scss/*.scss'),
        ],
        'web.report_assets_common': [
            'l10n_mx_hr_payroll_account_edi/static/src/scss/*.scss',
        ]
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
