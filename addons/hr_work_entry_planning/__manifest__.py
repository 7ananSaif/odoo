# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Work Entries - Planning',
    'category': 'Human Resources/Employees',
    'sequence': 95,
    'summary': 'Create work entries from the employee\'s planning',
    'installable': True,
    'auto_install': True,
    'depends': [
        'hr_work_entry_enterprise',
        'planning',
    ],
    'data': [
        'views/hr_employee_views.xml',
        'views/hr_contract_template_views.xml',
    ],
    'demo': [
        'data/hr_work_entry_planning_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
