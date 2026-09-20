# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Work Entries - Attendance',
    'category': 'Human Resources/Employees',
    'sequence': 95,
    'summary': 'Create work entries from the employee\'s attendances',
    'post_init_hook': '_generate_attendances',
    'depends': [
        'hr_work_entry',
        'hr_attendance',
    ],
    'data': [
        'data/hr_attendance_overtime_rule_data.xml',
        'views/hr_attendance_overtime_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_template_views.xml',
    ],
    'demo': [
        'data/hr_work_entry_attendance_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'installable': True,
    'auto_install': True,
}
