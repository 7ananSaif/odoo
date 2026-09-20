# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'DIN 5008 - Rental',
    'category': 'Accounting/Localizations',
    'depends': [
        'l10n_din5008',
        'sale_renting',
    ],
    'data': [
        'report/rental_order_report_templates.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
