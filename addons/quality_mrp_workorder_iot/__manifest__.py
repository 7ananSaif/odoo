# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'MRP features for Quality Control with IoT',
    'summary': 'Quality Management with MRP and IoT',
    'depends': ['quality_mrp_workorder', 'quality_control_iot', 'mrp_workorder_iot'],
    'category': 'Supply Chain/Quality',
    'description': """
    Adds Quality Control to workorders with IoT.
""",
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'quality_mrp_workorder_iot/static/src/**/*',
        ],
    }
}
