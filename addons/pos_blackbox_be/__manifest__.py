# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Belgian Registered Cash Register',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'Implements the registered cash system, adhering to guidelines by FPS Finance.',
    'description': """
Belgian Registered Cash Register
================================

This module turns the Point Of Sale module into a certified Belgian cash register.

More info:
  * http://www.systemedecaisseenregistreuse.be/
  * http://www.geregistreerdkassasysteem.be/

Legal
-----
Contact Odoo SA before installing pos_blackbox_be module.

No modified version is certified and supported by Odoo SA.
    """,
    'depends': ['pos_iot', 'l10n_be', 'web_enterprise', 'pos_hr', 'pos_restaurant', 'pos_discount', 'pos_self_order', 'pos_urban_piper'],
    'data': [
        'data/data.xml',
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/pos_blackbox_be_views.xml',
        'views/pos_daily_reports.xml',
        'views/pos_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
        'views/res_company_views.xml'
    ],
    'demo': [
        'data/demo.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_blackbox_be/static/src/pos/**/*',
            'pos_blackbox_be/static/src/common/**/*',
        ],
        'pos_self_order.assets': [
            'pos_blackbox_be/static/src/self_order/**/*',
            'pos_blackbox_be/static/src/common/**/*',
            'point_of_sale/static/lib/sha1.js',
        ],
    },
    'post_init_hook': '_set_tax_on_work_in_out',
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
