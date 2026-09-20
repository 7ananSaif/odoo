# -*- coding: utf-8 -*-
{
    'name': "Online Bank Statement Synchronization",
    'summary': "This module is used for Online bank synchronization.",

    'description': """
With this module, users will be able to link bank journals to their
online bank accounts (for supported banking institutions), and configure
a periodic and automatic synchronization of their bank statements.
    """,

    'category': 'Accounting/Accounting',
    'version': '1.0',
    'depends': ['account_accountant'],

    'data': [
        'data/config_parameter.xml',
        'data/ir_cron.xml',
        'data/mail_subtype_data.xml',
        'data/mail_template.xml',

        'security/ir.model.access.csv',
        'security/account_online_sync_security.xml',

        'views/account_online_sync_views.xml',
        'views/account_bank_statement_view.xml',
        'views/account_journal_view.xml',
        'views/account_online_sync_portal_templates.xml',
        'views/account_journal_dashboard_view.xml',

        'wizard/account_bank_selection_wizard.xml',
        'wizard/account_journal_missing_transactions.xml',
        'wizard/account_journal_duplicate_transactions.xml',
        'wizard/account_bank_statement_line.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            'account_online_synchronization/static/src/components/**/*',
            ('remove', 'account_online_synchronization/static/src/components/**/*.dark.scss'),
            'account_online_synchronization/static/src/hooks/**/*',
            'account_online_synchronization/static/src/js/odoo_fin_connector.js',
        ],
        'web.assets_web_dark': [
            'account_online_synchronization/static/src/components/**/*.dark.scss',
        ],
        'web.assets_frontend': [
            'account_online_synchronization/static/src/interactions/*',
        ],
        'web.assets_unit_tests': [
            'account_online_synchronization/static/tests/**/*',
        ],
    }
}
