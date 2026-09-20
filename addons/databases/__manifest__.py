{
    'name': 'Databases',
    'version': '1.0',
    'category': 'Services/Databases',
    'summary': 'Manage a fleet of Odoo databases',
    'description': """
Connect and manage all your client databases
============================================

The Databases app lets you connect and manage all your client databases from a
single Odoo workspace. Whether you are an accounting firm or an Odoo partner,
you can easily track who manages each database, follow up on timesheets, tasks
and more.
""",
    'depends': ['project'],
    'data': [
        'security/databases_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'data/project_template.xml',
        'views/databases_project_views.xml',
        'views/databases_menus.xml',
        'views/res_config_settings_views.xml',
        'wizard/databases_manage_users_wizard_views.xml',
        'wizard/databases_synchronization_wizard_views.xml',
        'wizard/project_template_create_wizard.xml',
    ],
    'application': True,
    'installable': True,
    'assets': {
        'web.assets_backend': [
            'databases/static/src/views/databases_project_list/databases_project_list_renderer.js',
            'databases/static/src/views/databases_project_list/databases_project_list_view.js',
        ],
        'web.assets_tests': [
            'databases/static/tests/tours/**/*',
        ],
    },
    'uninstall_hook': 'uninstall_hook',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
