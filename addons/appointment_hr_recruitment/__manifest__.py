# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Recruitment tracking on appointments",
    'version': "1.0",
    'category': 'Services/Appointment',
    'summary': "Keep track of recruitment appointments",
    'description': """
Keeps track of all appointments related to applicants.
""",
    'depends': ['appointment', 'hr_recruitment'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_tests': [
            'appointment_hr_recruitment/static/tests/tours/**/*',
        ],
    },
    'data': [
        'data/mail_template_data.xml',
    ],
    'demo': [
        'data/appointment_hr_recruitment_demo.xml',
    ],
}
