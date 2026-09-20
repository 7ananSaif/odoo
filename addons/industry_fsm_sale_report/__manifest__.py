# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Field Service Reports - Sale',
    'category': 'Services/Field Service',
    'summary': 'Create Reports for Field service technicians',
    'depends': ['industry_fsm_sale', 'industry_fsm_report'],
    'data': [
        'views/product_template_views.xml',
        'views/project_project_views.xml',
        'views/project_task_views.xml',
        'views/project_portal_project_task_templates.xml',
        'data/product_product_data.xml',
    ],
    'demo': [
        'data/product_product_demo.xml',
        'data/ir_model_fields_demo.xml',
        'data/ir_ui_view_demo.xml',
    ],
    'auto_install': True,
    'post_init_hook': 'post_init',
    'assets': {
        'web.assets_backend': [
            'industry_fsm_sale_report/static/src/js/tours/industry_fsm_sale_report_tour.js',
        ],
        'web.assets_frontend': [
            'industry_fsm_sale_report/static/src/js/tours/industry_fsm_sale_report_tour.js',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
