# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Sri Lanka - Accounting Reports",
    "version": "1.0",
    "category": "Accounting/Localizations/Reporting",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "description": """
Accounting reports for Sri Lanka
    """,
    "depends": [
        "l10n_lk",
        "account_reports",
    ],
    "data": [
        "data/balance_sheet_lk.xml",
        "data/profit_and_loss_lk.xml",
        "data/account_return_data.xml",
    ],
    "installable": True,
    "auto_install": True,
}
