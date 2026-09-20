# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Salary Configurator',
    'category': 'Human Resources',
    'summary': 'Sign Employment Contracts',
    'version': '2.1',
    'depends': [
        'hr_sign',
        'http_routing',
        'hr_recruitment',
        'sign',
    ],
    'data': [
        'security/hr_contract_salary_security.xml',
        'security/ir.model.access.csv',

        'wizard/refuse_offer_wizard.xml',

        'views/hr_contract_salary_templates.xml',
        'views/hr_contract_signatories_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_applicant_views.xml',
        'views/hr_job_views.xml',
        'views/res_config_settings_views.xml',
        'views/hr_contract_salary_benefit_views.xml',
        'views/hr_contract_salary_personal_info_views.xml',
        'views/hr_contract_salary_resume_views.xml',
        'views/hr_contract_salary_offer_views.xml',
        'views/hr_contract_salary_offer_refusal_reason_views.xml',
        'views/hr_contract_template_views.xml',
        'views/sign_template_views.xml',
        'views/hr_version_views.xml',

        'data/ir_cron_data.xml',
        'data/mail_template_data.xml',
        'data/mail_templates.xml',
        'data/hr_contract_salary_benefits_data.xml',
        'data/hr_contract_salary_personal_info_data.xml',
        'data/hr_contract_salary_resume_data.xml',
        'data/hr_contract_salary_offer_refusal_reason_data.xml',

        'report/hr_contract_recruitment_report_views.xml',
    ],
    'demo': [
        'data/hr_contract_salary_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_frontend': [
            'hr_contract_salary/static/src/scss/hr_contract_salary.scss',
            'hr_contract_salary/static/src/interactions/hr_contract_salary.js',
            'hr_contract_salary/static/src/xml/resume_sidebar.xml',
            'hr_contract_salary/static/src/xml/select_menu_wrapper_template.xml',
            'hr_contract_salary/static/src/xml/hr_contract_salary_select_menu_template.xml',
            'hr_contract_salary/static/src/js/hr_contract_salary_select_menu.js',
        ],
        'web.assets_backend': [
            'hr_contract_salary/static/src/js/binary_field_contract.js',
            'hr_contract_salary/static/src/xml/binary_field_contract.xml',
            'hr_contract_salary/static/src/js/url_field.js',
            'hr_contract_salary/static/src/xml/url_field.xml',
            'hr_contract_salary/static/src/js/copy_clipboard_field.js',
            'hr_contract_salary/static/src/scss/copy_clipboard_field.scss',
        ],
        'web.assets_tests': [
            'hr_contract_salary/static/tests/tours/hr_contract_salary_applicant_flow_tour.js',
            'hr_contract_salary/static/tests/tours/hr_contract_salary_employee_flow_tour.js',
        ]
    }
}
