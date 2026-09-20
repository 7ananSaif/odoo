# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Appraisal - Survey',
    'version': '1.2',
    'category': 'Human Resources/Appraisals',
    'sequence': 31,
    'summary': '360 Feedback',
    'website': 'https://www.odoo.com/app/appraisals',
    'depends': ['hr_appraisal', 'survey'],
    'description': """
This module adds an integration with Survey to ask feedbacks to any employee, based on a survey to fill.
    """,
    "data": [
        'wizard/appraisal_ask_feedback_views.xml',
        'wizard/appraisal_select_survey_views.xml',
        'views/hr_appraisal_views.xml',
        'views/hr_appraisal_template_views.xml',
        'views/survey_user_input_views.xml',
        'views/survey_survey_views.xml',
        'views/survey_templates_statistics.xml',
        'security/ir.model.access.csv',
        'security/hr_appraisal_survey_security.xml',
        'data/hr_appraisal_survey_data.xml',
        'data/mail_template_data.xml',
        'data/mail_message_subtype_data.xml',
    ],
    "demo": [
        'data/hr_appraisal_survey_demo.xml',
    ],
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
