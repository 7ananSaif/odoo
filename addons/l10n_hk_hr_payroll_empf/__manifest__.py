# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Hong Kong - Payroll eMPF',
    'countries': ['hk'],
    'category': 'Human Resources/Payroll',
    'depends': ['l10n_hk_hr_payroll'],
    'auto_install': ['l10n_hk_hr_payroll'],
    'description': """
Hong Kong Payroll eMPF.
========================
    """,
    'data': [
        'security/ir.model.access.csv',
        'security/l10n_hk_hr_payroll_empf.xml',

        'data/l10n_hk.mpf.scheme.csv',
        'data/hr_departure_reason_data.xml',
        'data/hr_payroll_dashboard_warning_data.xml',
        'data/cap57/employee_salary_data.xml',

        'views/hr_departure_reason_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_payslip_run_views.xml',
        'views/hr_version_views.xml',
        'views/l10n_hk_empf_contribution_views.xml',
        'views/member_class_views.xml',
        'views/mpf_scheme_views.xml',
        'views/res_config_settings_views.xml',

        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_hk_hr_payroll_empf/static/src/**/*',
        ],
    },
    'demo': [
        'demo/l10n_hk_hr_payroll_empf_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
