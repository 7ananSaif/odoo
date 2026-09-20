# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Recruitment With AI',
    'version': '1.0',
    'category': 'Human Resources/Recruitment',
    'depends': ['hr_recruitment', 'ai'],
    'auto_install': ['hr_recruitment', 'ai'],
    'data': [
        'wizard/applicant_refuse_reason_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
