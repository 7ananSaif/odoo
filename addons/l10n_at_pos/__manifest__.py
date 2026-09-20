{
    'name': "Austria - Security Regulation for Point of Sale",
    'summary': 'The Austrian Cash Security Regulation',
    'description': """
The Austrian Cash Security Regulation (RKSV - Registrierkassensicherheitsverordnung 2017).
==========================================================================================
* Creating the basis for a tamper-proof operation of cash registers in Austria.
* Complying with the legal regulations of RKSV.
* receipts issued in Austria must at least include the following data:

    * till identification number
    * date and time of receipt issuing
    * amount of cash payment per tax rate
    * this data must be included in the QR code
    * content of the machine-readable code

* DEP7 Data collection protocol (Datenerfassungsprotokoll). Each cash individual cash transaction is to be recorded and saved.

    * you can be able to export session's DEP7 reports

We have implemented all this using Fiskaly.
""",
    'version': '1.0',
    'depends': ['l10n_at', 'iap', 'point_of_sale'],
    'installable': True,
    'data': [
        'security/ir.model.access.csv',
        'views/res_company_view.xml',
        'views/pos_session_view.xml',
        'views/pos_order_view.xml',
        'views/pos_fiskaly_reports_template.xml',
        'wizard/pos_fiskaly_details.xml'
    ],
    'assets': {
        'web.assets_unit_tests': [
            'l10n_at_pos/static/tests/unit/**/*',
        ],
        'point_of_sale._assets_pos': [
            'l10n_at_pos/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
