# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Project - Sale',
    'version': '1.0',
    'category': 'Productivity/Documents',
    'summary': 'Products Folder Templates',
    'description': """
Adds the ability to set folder templates on products.
""",
    'depends': ['documents_project', 'sale_project'],
    'demo': [
        'data/documents_demo.xml',
        'data/project_sale_demo.xml',
        'data/res_users_settings_embedded_action_demo.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
