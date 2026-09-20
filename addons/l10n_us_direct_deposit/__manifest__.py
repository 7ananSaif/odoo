# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'United States - Direct Deposit',
    'countries': ['us'],
    'version': '1.0',
    'author': 'Odoo S.A.',
    'category': 'Accounting/Payment',
    'summary': 'Pay Vendors via Wise',
    'description': """
This module allows you to initiate batch payments directly in Odoo via Wise (https://wise.com).
Once a Wise account is created and credentials are added in Settings, vendor payments through batches
can be initiated digitally from within Odoo and redirect to be completed within Wise via Direct Debit ACH, Standard ACH, FedWire, or Wise Balance.
    """,
    'depends': [
        'account_batch_payment',
        'l10n_us',
    ],
    'data': [
        "data/l10n_us_direct_deposit_data.xml",
        "views/account_batch_payment_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_bank_views.xml",
    ],
    'installable': True,
    'license': 'OEEL-1',
}
