{
    'name': 'CFDI 4.0 fields for sale orders',
    'version': '1.0',
    'category': 'Accounting/Localizations/EDI',
    'depends': [
        'sale',
        'l10n_mx_edi',
    ],
    'data': [
        'report/sale_order_templates.xml',
        'views/sale_order_view.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
