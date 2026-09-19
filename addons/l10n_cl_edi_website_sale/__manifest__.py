# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Chilean eCommerce',
    'version': '0.0.1',
    'category': 'Accounting/Localizations/Website',
    'sequence': 14,
    'author': 'Blanco Martín & Asociados',
    'depends': [
        'website_sale',
        'l10n_cl_edi'
    ],
    'data': [
        'data/data.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'l10n_cl_edi_website_sale/static/src/interactions/**/*',
            'l10n_cl_edi_website_sale/static/src/js/invoicing_info.js',
        ]
    },
    'license': 'OEEL-1',
    'post_init_hook': '_post_init_hook',
}
