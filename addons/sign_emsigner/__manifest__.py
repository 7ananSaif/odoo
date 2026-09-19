# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sign emSigner',
    'version': '1.0',
    'category': 'Sales/Sign',
    'summary': "Sign documents with emSigner",
    'description': "Add support for emSigner identification when signing documents (Indian only)",
    'depends': ['sign', 'iap'],
    'data': [
        'data/iap_service_data.xml',
        'report/sign_emsigner_log_reports.xml',
        'views/sign_request_templates.xml'
    ],
    'assets': {
        'sign.assets_public_sign': [
            'sign_emsigner/static/src/components**/*',
            'sign_emsigner/static/src/dialogs**/*',
        ],
        'web.assets_backend': [
            'sign_emsigner/static/src/**/*',
        ],
        'web.assets_frontend': [
            'sign_emsigner/static/src/components**/*',
            'sign_emsigner/static/src/dialogs**/*',
        ],
    },
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
