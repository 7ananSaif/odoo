{
    'name': 'Account Bank Statement Extract',
    'category': 'Accounting/Accounting',
    'version': '1.0',
    'depends': ['accountant', 'account_bank_statement_import', 'iap_extract', 'account_extract'],
    'summary': 'Extract data from bank statement scans to fill them automatically',
    'data': [
        'views/res_config_settings_views.xml',
        'views/account_bank_statement_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_bank_statement_extract/static/src/js/*.js',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
