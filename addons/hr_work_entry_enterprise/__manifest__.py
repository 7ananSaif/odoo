# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Work Entries - Enterprise',
    'category': 'Human Resources/Employees',
    'sequence': 39,
    'summary': 'Manage work entries',
    'installable': True,
    'depends': [
        'hr_work_entry',
        'hr_gantt',
    ],
    'data': [
        'views/hr_payroll_menu.xml',
        'views/hr_work_entry_views.xml',
    ],
    'auto_install': True,
    'assets': {
        'web.assets_backend_lazy': [
            'hr_work_entry_enterprise/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'hr_work_entry_enterprise/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
