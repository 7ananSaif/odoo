# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Odoo Mexico Localization for Stock/Landing',
    'countries': ['mx'],
    'summary': 'Generate Electronic Invoice with custom numbers',
    'version': '1.0',
    'category': 'Accounting/Localizations/EDI',
    'depends': [
        'stock_landed_costs',
        'sale_management',
        'sale_stock',
        'l10n_mx_edi_extended',
    ],
    'data': [
        'views/stock_landed_cost.xml',
        'views/stock_lot_views.xml',
        'views/stock_move_line_views.xml',
        'views/stock_quant_views.xml',
        'views/account_move_views.xml',
        'views/product_template_views.xml',
        'views/report_invoice.xml',
    ],
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
