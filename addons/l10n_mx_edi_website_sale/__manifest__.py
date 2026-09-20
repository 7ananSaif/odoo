# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mexican Localization for eCommerce',
    'description': '''
Add an extra tab in the checkout process of the website/eCommerce with the mexican fields:

- l10n_mx_edi_cfdi_to_public (sale.order/account.move)
- l10n_mx_edi_fiscal_regime (res.partner)
- l10n_mx_edi_usage (sale.order/account.move)
- l10n_mx_edi_ieps_breakdown (res.partner)

The extra tab only appears if:

- the company linked to the website is mexican
- the option 'automatic_invoice' is enabled in the website settings ("Invoice automatically on payment")
    ''',
    'version': '1.0',
    'category': 'Accounting/Localizations/EDI',
    'depends': [
        'website_sale',
        'l10n_mx_edi_sale',
    ],
    'data': [
        'data/data.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'l10n_mx_edi_website_sale/static/src/interactions/**/*',
            'l10n_mx_edi_website_sale/static/src/js/invoicing_info.js',
        ],
        'web.assets_tests': [
            'l10n_mx_edi_website_sale/static/tests/tours/*.js',
        ],
    },
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_post_init_hook',
}
