# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - HR',
    'version': '1.0',
    'category': 'Productivity/Documents',
    'summary': 'Access documents from the employee profile',
    'description': """
Easily access your documents from your employee profile.
""",
    'website': ' ',
    'depends': ['documents', 'hr'],
    'data': [
        'data/documents_tag_data.xml',
        'data/res_company_data.xml',
        'views/documents_templates_portal.xml',
        'views/res_config_settings_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_employee_public_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_documents_hr_post_init',
}
