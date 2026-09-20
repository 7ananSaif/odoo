# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Netherlands Intrastat Declaration',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Generates Netherlands Intrastat report for declaration based on invoices
and submit your Intracommunity Services to the Dutch tax authorities.
    """,
    'depends': ['l10n_nl_reports', 'account_intrastat'],
    'data': [
        'views/res_company_view.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
