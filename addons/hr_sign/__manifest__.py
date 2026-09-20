# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Contract - Signature',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Manage your documents to sign in contracts',
    'depends': ['hr', 'sign'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/hr_contract_sign_document_wizard_view.xml',
        'views/hr_employee_view.xml',
        'views/hr_employee_public_views.xml',
        'views/sign_request_views.xml',
        'views/mail_activity_plan_views.xml',
        'views/mail_activity_plan_template_views.xml',
        'data/hr_sign_data.xml',
    ],
    'demo': [
        'data/hr_sign_demo.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
