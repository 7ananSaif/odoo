{
    'name': 'Electronic invoicing for Colombia with DIAN',
    'version': '1.1',
    'category': 'Accounting/Localizations/EDI',
    'summary': 'Colombian Localization for EDI documents',
    'depends': [
        'account_edi_ubl_cii',
        'l10n_co_edi',
        'certificate',
    ],
    'data': [
        'data/mail_template_data.xml',
        'data/product_product.xml',
        'security/ir.model.access.csv',
        'wizard/l10n_co_dian_claim_wizard.xml',
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'views/l10n_co_dian_operation_mode.xml',
        'views/report_invoice.xml',
        'views/res_config_settings_views.xml',
        'views/templates.xml',
        'views/res_partner_views.xml',
        'data/cron.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'auto_install': ['l10n_co_edi'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'l10n_co_dian/static/src/scss/**/*',
        ],
        'web.report_assets_common': [
            'l10n_co_dian/static/src/scss/**/*',
        ],
    }
}
