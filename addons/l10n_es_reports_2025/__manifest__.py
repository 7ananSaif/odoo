# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spain - Accounting Reports (2025 Update)",
    'description': """
        Backports the tax return functionalities in the Spanish localization
    """,
    'category': 'Accounting/Localization',
    'version': '1.0',
    'depends': ['l10n_es_reports'],
    'data': [
        'security/ir.model.access.csv',
        'data/account_return_data.xml',
        'wizard/l10n_es_return_submission_wizards.xml',
        'wizard/l10n_es_boe_wizard_validation.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
