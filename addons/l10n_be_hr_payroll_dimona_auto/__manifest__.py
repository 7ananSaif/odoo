# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Belgium - Payroll - Dimona - Automation',
    'countries': ['be'],
    'category': 'Human Resources',
    'depends': ['l10n_be_hr_payroll_dimona', 'l10n_be_hr_payroll'],
    'description': """
Automatic DIMONA declarations
=============================

Prerequisites:
--------------

- You need a Belgian Government Compliant Digital Certificate, delivered by Global
  Sign. See: https://shop.globalsign.com/en/belgian-government-services

- Generate certificate files from your SSL certificate (.pfx file) that are needed to create
  a technical user (.cer file) and to authenticate remotely to the ONSS (.pfx) file. On a UNIX
  system, you may use the following commands:

  - PFX -> CRT: openssl pkcs12 -in my_cert.pfx -out my_cert.crt -nokeys -clcerts

  - CRT -> CER: openssl x509 -inform pem -in my_cert.crt -outform der -out my_cert.cer

- Before you can use the social security REST web service, you must create an account
  for yourself or for your client and configure the security. (The whole procedure is
  available at https://www.socialsecurity.be/site_fr/employer/applics/dimona/introduction/webservice.htm)

  - User account management: Follow the Procedure https://www.socialsecurity.be/site_fr/general/helpcentre/rest/documents/pdf/procedure_pour_gestion_des_acces_UMan_FR.pdf

  - Create a technical user: Your client must now create a technical user in the Access management
    online service. The follow this procedure: https://www.socialsecurity.be/site_fr/general/helpcentre/rest/documents/pdf/webservices_creer_le_canal_FR.pdf

  - Activate a web service channel: Once the technical user has been created, your client must
    activate the web service channel in Access Management. The following manual explains the
    steps to follow to activate the channel: https://www.socialsecurity.be/site_fr/general/helpcentre/rest/documents/pdf/webservices_ajouter_le_canal_FR.pdf

  - At the end of the procedure, you should receive a "ONSS Expeditor Number", you may
    encode in in the payroll Settings, with the .pem file and the related password, if any.

- Configuration note: The .pfx certificate should be set on the payroll configuration.
    """,
    'data': [
        'data/ir_actions_server_data.xml',
        'security/ir.model.access.csv',
        'security/l10n_be_hr_payroll_dimona_auto_security.xml',
        'views/hr_employee_views.xml',
        'views/l10n_be_dimona_declaration_views.xml',
        'views/l10n_be_dimona_period_views.xml',
        'views/l10n_be_dimona_relation_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': ['l10n_be_hr_payroll'],
}
