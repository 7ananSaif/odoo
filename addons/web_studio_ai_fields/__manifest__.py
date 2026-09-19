# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "web_studio_ai_fields",
    'summary': "Enable creating AI computed fields in studio",
    'description': "Enable Ai fields configuration in studio",
    'category': 'Hidden',
    'version': '0.1',
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'depends': ['ai_fields', 'web_studio'],
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            'web_studio_ai_fields/static/src/**/*.xml',
        ],
        'web_studio.studio_assets_minimal': [
            'web_studio_ai_fields/static/src/**/*.js',
            'web_studio_ai_fields/static/src/**/*.scss',
        ],
        'web.assets_unit_tests': [
            'web_studio_ai_fields/static/tests/**/*',
        ],
    },
}
