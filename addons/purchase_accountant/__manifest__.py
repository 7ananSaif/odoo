# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Purchase Accounting",
    'version': "1.0",
    'category': "Supply Chain/Purchase",
    'summary': "Bridge between Purchase and Accounting",
    'description': """
Add accrued menus and specific filters on purchase order lines for an easier closing process.
    """,
    'depends': ['purchase', 'account_accountant'],
    'data': [
        'views/purchase_order_line_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
