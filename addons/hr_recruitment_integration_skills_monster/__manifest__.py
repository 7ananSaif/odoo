# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Job Board - Monster.com (Skills)',
    'version': '1.0',
    'category': 'Human Resources/Recruitment/Integration',
    'summary': 'Manage Monster Job board integrations with skills',
    'description': """
Module for Monster integration with skills.
===========================================
This module allows to automatically adds the skills from the job offers
to the Monster job posts.
""",
    'depends': [
        'hr_recruitment_skills',
        'hr_recruitment_integration_monster',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
