{
    'name': 'Belgian Intervat & Myminfin Edi',
    'version': '1.0',
    'category': 'Accounting/Localizations/edi',
    'description': """
Integration with Intervat & MyMinfin APIs, allowing to send and receive
your electronic VAT declarations.
    """,
    'depends': ['l10n_be', 'l10n_be_reports', 'certificate'],
    'data': [
        'security/ir.model.access.csv',
        'security/l10n_be_vat_declaration_rules.xml',
        'views/account_return_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/vat_return_lock_wizard.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'installable': True,
    'auto_install': ['l10n_be', 'l10n_be_reports'],
    'license': 'OEEL-1',
    'author': 'Odoo SA',
}
