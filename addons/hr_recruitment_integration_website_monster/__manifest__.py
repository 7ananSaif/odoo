# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Job Board - Monster.com (Website)',
    'version': '1.0',
    'category': 'Human Resources/Recruitment/Integration',
    'summary': 'Manage Monster Job board integrations with website',
    'description': """
Module for Monster integration with website.
=========================================================================
This module allows to adapt the monster job board integrations with online
recruitment by providing the possibility to redirect the job offers on your
website from Monster job post.
""",
    'depends': [
        'hr_recruitment_integration_website',
        'hr_recruitment_integration_monster',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
