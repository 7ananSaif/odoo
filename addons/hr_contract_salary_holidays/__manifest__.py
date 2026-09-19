# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Salary Configurator - Holidays',
    'category': 'Human Resources',
    'summary': 'Automatically creates extra time-off on contract signature',
    'depends': [
        'hr_contract_salary',
        'hr_holidays',
    ],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
