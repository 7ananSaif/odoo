# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Repair features for Quality Control',
    'version': '1.0',
    'category': 'Supply Chain/Quality',
    'sequence': 50,
    'summary': 'Quality Management with Repair',
    'depends': ['quality_control', 'repair'],
    'description': """
Adds repair orders to Quality Control
    """,
    "data": [
        'views/quality_views.xml',
        'views/repair_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
