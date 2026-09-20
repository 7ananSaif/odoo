# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Job Board - Monster.com',
    'version': '1.0',
    'category': 'Human Resources/Recruitment/Integration',
    'summary': 'Allow user to share job positions on Monster Job board',
    'description': """
Module for monster integration
==============================
This module provides a base for the integration of recruitment with the external
api from Monster.
""",
    'depends': [
        'hr_recruitment_integration_base',
        'hr_recruitment_extract',
    ],
    'data': [
        'data/hr_recruitment_platform_data.xml',
        'data/res_currency_data.xml',
        'data/hr_contract_type_data.xml',
        'data/res_partner_industry_data.xml',
        'views/res_currency_views.xml',
        'views/res_partner_industry_views.xml',
        'views/hr_contract_type_views.xml',
        'views/res_config_settings.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
