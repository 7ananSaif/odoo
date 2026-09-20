# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Employees in Gantt',
    'category': 'Human Resources/Employees',
    'summary': 'Employees in Gantt',
    'version': '1.0',
    'description': """ """,
    'depends': ['hr', 'web_gantt'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend_lazy': [
            'hr_gantt/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'hr_gantt/static/tests/**/*',
        ],
    }
}
