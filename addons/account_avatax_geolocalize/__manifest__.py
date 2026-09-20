# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Avatax for geo localization',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'depends': ['account_avatax', 'base_geolocalize'],
    'data': [
        'views/res_partner_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
